"""
O.R.E.L.I.U.S. Core Engine
The heart of the autonomous AI agent system.

Rebuilt to run on Claude Haiku 4.5 with a credit-saving layer (response cache,
history trimming, prompt caching, dynamic output caps) and a shared-memory link
to its companion system LUCIUS.
"""
import re
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from .claude_client import claude_client
from .memory_manager import memory_manager
from .security import security_layer
from .prompts import get_system_prompt
from .token_optimizer import token_optimizer
from .shared_memory import shared_memory
from .persona_profile import persona_profile
from . import athena
from ..models.conversation import MessageRole, MessageSource
from ..models.audit_log import AuditEventType, AuditSeverity
from ..config import settings
from ..utils.logger import logger


# When any of these appear, the Master clearly wants design/content work done by
# ATHENA — so we FORCE the athena_design tool instead of letting the brain reply
# in prose (a small model tends to "role-play" delegating without actually doing it).
_ATHENA_INTENT = re.compile(
    r"\b(athena|instagram|\big\b|reel|reels|carousel|caption|post|posts|publish|"
    r"content|design|graphic|graphics|branding|mockup|flyer|banner|story|stories)\b",
    re.IGNORECASE,
)


def wants_athena(message: str) -> bool:
    """True if the message is a design/content request ORELIUS should hand to ATHENA."""
    return bool(_ATHENA_INTENT.search(message or ""))


class OreilusEngine:
    """
    O.R.E.L.I.U.S. Core Engine
    Coordinates all agent capabilities: Claude API, memory, security, reporting,
    credit optimization, and the LUCIUS shared-memory companion link.
    """

    def __init__(self):
        self.system_prompt = get_system_prompt(full=True)
        self.claude = claude_client
        self.memory = memory_manager
        self.security = security_layer
        self.optimizer = token_optimizer
        self.shared = shared_memory
        self.persona = persona_profile

    async def process_message(
        self,
        db: AsyncSession,
        user_id: str,
        user_message: str,
        source: MessageSource = MessageSource.WEB,
        stream: bool = False,
        attachments: list[dict] | None = None,
    ) -> str | AsyncGenerator[str, None]:
        """Process incoming message from user."""
        try:
            # SECURITY: validate user authorization for all message sources
            # (string IDs so web logins like "anthony" work alongside numeric Telegram IDs)
            allowed_users = settings.allowed_login_ids

            is_safe, threat, audit_event, severity = await self.security.check_message_security(
                user_message,
                user_id,
                allowed_users,
            )

            await self.memory.log_audit(
                db,
                event_type=audit_event,
                description=threat if not is_safe else "Message received successfully",
                user_id=user_id,
                severity=severity,
                event_metadata={"source": source.value, "message_length": len(user_message)},
            )

            if not is_safe:
                logger.warning(f"Security check failed for user {user_id}: {threat}")
                return f"Security alert: {threat}. This incident has been logged."

            # Get or create conversation
            conversation = await self.memory.get_or_create_conversation(db, user_id, source)

            # Add user message to database
            await self.memory.add_message(
                db,
                conversation.id,
                MessageRole.USER,
                user_message,
            )

            # Conversation history, trimmed to control token spend
            history = await self.memory.get_conversation_history(db, conversation.id)
            history = self.optimizer.trim_history(history)

            # Pull the latest shared LUCIUS/ORELIUS memory to inject into the persona
            shared_context = await self.shared.build_context(db)
            # Pull ORELIUS's learned read of the Master's personality (chat only).
            persona_context = await self.persona.render_context(db)

            logger.info(f"Generating response for user {user_id} (conversation {conversation.id})")

            if stream and not attachments:
                return self._stream_response(
                    db, conversation.id, history, user_message, shared_context, persona_context
                )
            reply = await self._complete_response(
                db, conversation.id, history, user_message, shared_context, attachments, persona_context
            )
            # Learn the Master's personality from this exchange (cheap, throttled,
            # and strictly conversational — never touches the finance automation).
            await self.persona.observe(db, history, user_message, reply)
            return reply

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await self.memory.log_audit(
                db,
                event_type=AuditEventType.SECURITY_ALERT,
                description=f"Error processing message: {str(e)}",
                user_id=user_id,
                severity=AuditSeverity.ERROR,
            )
            return (
                "I apologize, Master. An internal error occurred while processing your "
                "request. The issue has been logged for review."
            )

    async def _complete_response(
        self,
        db: AsyncSession,
        conversation_id: int,
        history: list[dict],
        user_message: str,
        shared_context: str = "",
        attachments: list[dict] | None = None,
        persona_context: str = "",
    ) -> str:
        """Generate complete response (non-streaming) with response-cache short-circuit."""
        system = self.system_prompt + shared_context + persona_context

        # 0) Attachments (photos / files): vision path. No cache, no tools — the
        #    Master sent media to look at, so answer directly with the image/file.
        if attachments:
            return await self._respond_with_attachments(
                db, conversation_id, system, history, user_message, attachments
            )

        athena_request = settings.athena_enabled and wants_athena(user_message)

        # 1) Credit saver: identical repeat question? serve from cache for 0 credits.
        #    Never cache-serve a design/ATHENA request — it must reach the tool, not
        #    replay an old canned "forwarded to ATHENA" reply.
        cache_key = self.optimizer.cache_key(system, history)
        if not athena_request:
            cached = self.optimizer.get_cached_response(cache_key)
            if cached is not None:
                logger.info("Served response from cache (0 credits used)")
                self.optimizer.usage.record_cache_hit(
                    would_be_input=self.claude.count_messages_tokens(history),
                    would_be_output=self.claude.count_tokens(cached),
                )
                await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, cached)
                return cached

        max_tokens = self.optimizer.choose_max_tokens(user_message)

        # 2) Live call. When ATHENA is enabled, offer the design-delegation tool so
        #    ORELIUS can hand design work to ATHENA in a single model turn. If the
        #    message is clearly a design request, FORCE the tool so ORELIUS actually
        #    dispatches to ATHENA instead of just talking about it.
        if settings.athena_enabled:
            handled = await self._respond_with_athena(
                db, conversation_id, system, history, user_message, max_tokens, cache_key,
                force_tool=athena_request,
            )
            if handled is not None:
                return handled

        # Plain reply path (no tools) — also the fallback if the tools call fails.
        response = await self.claude.chat(
            messages=history,
            system_prompt=system,
            stream=False,
            max_tokens=max_tokens,
        )

        self.optimizer.store_response(cache_key, response)
        await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, response)
        await self._record_shared_memory(db, user_message, response)
        return response

    async def _respond_with_attachments(
        self,
        db: AsyncSession,
        conversation_id: int,
        system: str,
        history: list[dict],
        user_message: str,
        attachments: list[dict],
    ) -> str:
        """Answer a message that carries photos/files (Haiku 4.5 vision + files)."""
        import base64

        text_parts: list[str] = [user_message] if user_message else []
        media_blocks: list[dict] = []
        names: list[str] = []
        for att in attachments:
            mt = (att.get("media_type") or "").lower()
            name = att.get("name") or "file"
            data = att.get("data") or ""
            names.append(name)
            if mt.startswith("image/"):
                media_blocks.append(
                    {"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}}
                )
            elif mt == "application/pdf":
                media_blocks.append(
                    {"type": "document", "source": {"type": "base64", "media_type": mt, "data": data}}
                )
            elif mt.startswith("text/") or mt in ("application/json", "application/csv"):
                try:
                    decoded = base64.b64decode(data).decode("utf-8", errors="replace")[:12000]
                    text_parts.append(f"\n\n[Attached file: {name}]\n{decoded}")
                except Exception:  # noqa: BLE001
                    text_parts.append(f"\n\n[Attached file {name} could not be read]")
            else:
                text_parts.append(f"\n\n[Attached: {name} ({mt}) — not directly viewable]")

        content_blocks: list[dict] = [
            {"type": "text", "text": "\n".join(p for p in text_parts if p) or "Please review the attached file(s), Master."}
        ] + media_blocks

        messages = list(history)
        if messages and messages[-1].get("role") == "user":
            messages[-1] = {"role": "user", "content": content_blocks}
        else:
            messages.append({"role": "user", "content": content_blocks})

        try:
            response = await self.claude.chat(
                messages=messages,
                system_prompt=system,
                stream=False,
                max_tokens=settings.oreilus_report_max_tokens,
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"attachment response failed: {e}")
            response = "I received your attachment, Master, but could not process it this time. Please try again."

        await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, response)
        summary = user_message or f"reviewed attachment(s): {', '.join(names)[:200]}"
        await self._record_shared_memory(db, summary, response)
        return response

    async def _respond_with_athena(
        self,
        db: AsyncSession,
        conversation_id: int,
        system: str,
        history: list[dict],
        user_message: str,
        max_tokens: int,
        cache_key: str,
        force_tool: bool = False,
    ) -> Optional[str]:
        """Model turn that may delegate design work to ATHENA.

        Returns the reply text if this path produced one (whether or not a design
        job was dispatched), or None to signal the caller to fall back to the
        plain, tool-less reply path (e.g. on an API error). When `force_tool` is
        set, the model is required to call athena_design (used when the message is
        clearly a design request), guaranteeing an actual dispatch.
        """
        tool_choice = {"type": "tool", "name": "athena_design"} if force_tool else None
        try:
            resp = await self.claude.complete_with_tools(
                messages=history,
                system_prompt=system,
                tools=[athena.ATHENA_TOOL],
                max_tokens=max_tokens,
                tool_choice=tool_choice,
            )
        except Exception as e:  # noqa: BLE001 - fall back to a normal reply
            logger.warning(f"ATHENA tool turn failed, using plain reply: {e}")
            return None

        # Collect any spoken text and the first athena_design tool call.
        preface_parts: list[str] = []
        tool_call = None
        for block in getattr(resp, "content", []) or []:
            btype = getattr(block, "type", None)
            if btype == "text":
                preface_parts.append(getattr(block, "text", "") or "")
            elif btype == "tool_use" and getattr(block, "name", "") == "athena_design":
                tool_call = block

        if tool_call is None:
            # No design work — behave like a normal completion (cache + persist).
            reply = "\n".join(p for p in preface_parts if p).strip()
            if not reply:
                return None  # nothing usable; let the plain path handle it
            self.optimizer.store_response(cache_key, reply)
            await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, reply)
            await self._record_shared_memory(db, user_message, reply)
            return reply

        # Dispatch the job to ATHENA via shared memory (bridge picks it up).
        args = getattr(tool_call, "input", None) or {}
        request_text = str(args.get("request") or args.get("brief") or user_message)
        kind = args.get("kind")
        task = args.get("task")
        action = args.get("action")
        days = args.get("days")
        await athena.enqueue_design_request(
            db, request=request_text, kind=kind, task=task, action=action, days=days
        )

        reply = athena.confirmation_text(
            request=request_text,
            kind=kind or "design",
            preface="\n".join(p for p in preface_parts if p).strip(),
        )
        # Design dispatches are one-off; don't cache the confirmation.
        await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, reply)
        await self._record_shared_memory(db, user_message, reply)
        return reply

    async def _stream_response(
        self,
        db: AsyncSession,
        conversation_id: int,
        history: list[dict],
        user_message: str,
        shared_context: str = "",
        persona_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response."""
        system = self.system_prompt + shared_context + persona_context
        full_response = ""

        async for chunk in await self.claude.chat(
            messages=history,
            system_prompt=system,
            stream=True,
            max_tokens=self.optimizer.choose_max_tokens(user_message),
        ):
            full_response += chunk
            yield chunk

        # persist + cache + share once streaming completes
        self.optimizer.store_response(self.optimizer.cache_key(system, history), full_response)
        await self.memory.add_message(db, conversation_id, MessageRole.ASSISTANT, full_response)
        await self._record_shared_memory(db, user_message, full_response)
        # Learn the Master's personality from this exchange (chat only).
        await self.persona.observe(db, history, user_message, full_response)

    async def _record_shared_memory(self, db: AsyncSession, user_message: str, response: str) -> None:
        """Write a compact exchange summary to the LUCIUS/ORELIUS shared log."""
        try:
            await self.shared.remember(
                db,
                content=f"Master asked: {user_message[:280]} | ORELIUS advised: {response[:280]}",
                kind="exchange",
                actor="ORELIUS",
            )
        except Exception as e:  # noqa: BLE001 - shared memory must never break a reply
            logger.debug(f"shared memory write skipped: {e}")

    async def validate_system(self) -> dict:
        """Validate that O.R.E.L.I.U.S. is operational."""
        status = {
            "system": "O.R.E.L.I.U.S.",
            "model": settings.oreilus_model,
            "status": "operational",
            "components": {},
        }

        try:
            claude_valid = await self.claude.validate_api_key()
            status["components"]["claude_api"] = "operational" if claude_valid else "error"
        except Exception as e:
            status["components"]["claude_api"] = f"error: {str(e)}"
            status["status"] = "degraded"

        status["components"]["security_layer"] = "operational"
        status["components"]["memory_manager"] = "operational"
        status["components"]["shared_memory_lucius"] = "operational"
        status["components"]["token_optimizer"] = "operational"

        logger.info(f"System validation: {status['status']}")
        return status

    def optimization_stats(self) -> dict:
        """Expose credit-saver stats (for the dashboard / cost visibility)."""
        return self.optimizer.stats()


# Global O.R.E.L.I.U.S. engine instance
oreilus_engine = OreilusEngine()
