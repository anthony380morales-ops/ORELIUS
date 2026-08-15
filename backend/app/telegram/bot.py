"""
Telegram Bot for O.R.E.L.I.U.S.
Optional mobile chat access via Telegram. Enabled only when TELEGRAM_BOT_TOKEN is set.
"""
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ..config import settings
from ..database import AsyncSessionLocal
from ..core import oreilus_engine
from ..models.conversation import MessageSource
from ..utils.logger import logger


class OreilusTelegramBot:
    """Telegram bot for O.R.E.L.I.U.S."""

    def __init__(self):
        self.token = settings.telegram_bot_token
        self.allowed_users = settings.allowed_telegram_users
        self.application = None

    def _authorized(self, user_id: str) -> bool:
        if not self.allowed_users:
            return True
        try:
            return int(user_id) in self.allowed_users
        except (TypeError, ValueError):
            return False

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = str(update.effective_user.id)
        if not self._authorized(user_id):
            await update.message.reply_text(
                "⛔ Unauthorized access. This bot is restricted to authorized users only."
            )
            logger.warning(f"Unauthorized Telegram access attempt: {user_id}")
            return

        welcome_message = """
🤖 **O.R.E.L.I.U.S. ACTIVATED**

_Optimized Revenue Engine & Intelligent Logistics Unified System_

Good to see you, Master. I am operational and at your service.

**Commands:**
/start - Initialize system
/status - System status check
/help - Command reference
/dashboard - Dashboard access info

Send me a direct message for strategic consultation, business intelligence, or
systems optimization. Awaiting your command.
"""
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        logger.info(f"Telegram bot started for user {user_id}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = str(update.effective_user.id)
        if not self._authorized(user_id):
            await update.message.reply_text("⛔ Unauthorized")
            return

        status = await oreilus_engine.validate_system()
        status_message = f"""
🟢 **SYSTEM STATUS: {status['status'].upper()}**

**Core Components:**
• Claude API: {status['components'].get('claude_api', 'unknown')}
• Security Layer: {status['components'].get('security_layer', 'unknown')}
• Memory Manager: {status['components'].get('memory_manager', 'unknown')}
• LUCIUS Shared Memory: {status['components'].get('shared_memory_lucius', 'unknown')}

All systems nominal. Ready for operation.
"""
        await update.message.reply_text(status_message, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
📚 **O.R.E.L.I.U.S. COMMAND REFERENCE**

/start - Initialize system connection
/status - Check system health
/help - Display this reference
/dashboard - Get dashboard access information

**Direct Messaging:**
Send me a message for strategic consultation, market intelligence, systems
optimization, security advisory, and LUCIUS / GREECE / ION Systems support.
"""
        await update.message.reply_text(help_message, parse_mode="Markdown")

    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /dashboard command - Provide dashboard access information"""
        user_id = str(update.effective_user.id)
        if not self._authorized(user_id):
            await update.message.reply_text("⛔ Unauthorized")
            return

        message = f"""
🖥️ **O.R.E.L.I.U.S. DASHBOARD ACCESS**

**Dashboard URL:**
`{settings.frontend_url}`

The dashboard offers the full interface: live chat, system status, security
settings, and audit logs. The Telegram bot gives you quick access on the go.
"""
        await update.message.reply_text(message, parse_mode="Markdown")
        logger.info(f"Dashboard info requested by user {user_id}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages"""
        user_id = str(update.effective_user.id)
        user_message = update.message.text

        if not self._authorized(user_id):
            await update.message.reply_text("⛔ Unauthorized")
            logger.warning(f"Unauthorized Telegram message from {user_id}")
            return

        logger.info(f"Telegram message from {user_id}: {user_message[:50]}...")
        await update.message.chat.send_action("typing")

        try:
            async with AsyncSessionLocal() as db:
                response = await oreilus_engine.process_message(
                    db=db,
                    user_id=user_id,
                    user_message=user_message,
                    source=MessageSource.TELEGRAM,
                    stream=False,
                )
                await update.message.reply_text(response, parse_mode="Markdown")
                await db.commit()
        except Exception as e:
            logger.error(f"Telegram message processing error: {e}")
            await update.message.reply_text(
                "⚠️ An error occurred while processing your request. The issue has been logged."
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Telegram bot error: {context.error}")

    def setup(self):
        """Setup bot handlers"""
        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("dashboard", self.dashboard_command))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        )
        self.application.add_error_handler(self.error_handler)
        logger.info("Telegram bot handlers configured")

    async def start(self):
        """Start the bot"""
        if not self.application:
            self.setup()
        logger.info("Starting Telegram bot...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Telegram bot is now running")

    async def stop(self):
        """Stop the bot"""
        if self.application:
            logger.info("Stopping Telegram bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")


# Global bot instance
telegram_bot = OreilusTelegramBot()
