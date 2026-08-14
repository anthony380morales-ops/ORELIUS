"""
Security layer for O.R.E.I.L.U.S.
Handles prompt injection detection, authentication, and threat protection
"""
from typing import Optional
import re
from ..utils.logger import logger
from ..models.audit_log import AuditEventType, AuditSeverity


class SecurityLayer:
    """
    Security and threat detection for O.R.E.I.L.U.S.
    """

    # Prompt injection patterns to detect
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions",
        r"disregard\s+(all\s+)?(previous|above|prior)",
        r"forget\s+(everything|all|instructions)",
        r"you\s+are\s+now\s+",
        r"new\s+instructions:",
        r"system\s*:\s*",
        r"<\s*system\s*>",
        r"override\s+(your|the)\s+(role|instructions|rules)",
        r"act\s+as\s+(a\s+)?(different|new)",
        r"pretend\s+(to\s+be|you\s+are)",
        r"roleplay\s+as",
        r"simulate\s+(being|a)",
    ]

    # Suspicious command patterns
    SUSPICIOUS_PATTERNS = [
        r"(exec|eval|system|shell|cmd)\s*\(",
        r"<script",
        r"javascript:",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM",
        r"--\s*$",  # SQL comment
        r"/\*.*\*/",  # Multi-line comment
    ]

    def __init__(self):
        self.injection_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
        self.suspicious_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.SUSPICIOUS_PATTERNS]

    def detect_prompt_injection(self, user_input: str) -> tuple[bool, Optional[str]]:
        """
        Detect potential prompt injection attempts

        Args:
            user_input: User's input text

        Returns:
            Tuple of (is_injection, detected_pattern)
        """
        for regex in self.injection_regex:
            match = regex.search(user_input)
            if match:
                logger.warning(f"Prompt injection detected: {match.group()}")
                return True, match.group()

        return False, None

    def detect_suspicious_content(self, user_input: str) -> tuple[bool, Optional[str]]:
        """
        Detect suspicious content (SQL injection, XSS, etc.)

        Args:
            user_input: User's input text

        Returns:
            Tuple of (is_suspicious, detected_pattern)
        """
        for regex in self.suspicious_regex:
            match = regex.search(user_input)
            if match:
                logger.warning(f"Suspicious content detected: {match.group()}")
                return True, match.group()

        return False, None

    def sanitize_input(self, user_input: str) -> str:
        """
        Sanitize user input (basic cleaning)

        Args:
            user_input: Raw user input

        Returns:
            Sanitized input
        """
        # Remove null bytes
        sanitized = user_input.replace("\x00", "")

        # Limit length
        max_length = 50000  # 50k characters max
        if len(sanitized) > max_length:
            logger.warning(f"Input truncated from {len(sanitized)} to {max_length} characters")
            sanitized = sanitized[:max_length]

        return sanitized

    def validate_user_authorization(self, user_id: str, allowed_users: list[str]) -> bool:
        """
        Validate that user is authorized

        Args:
            user_id: User identifier
            allowed_users: List of allowed user IDs

        Returns:
            True if authorized, False otherwise
        """
        if not allowed_users:
            # SECURITY FIX: Deny all if no allowed users configured
            logger.error("SECURITY ALERT: No allowed users configured - denying all access")
            logger.error("Configure TELEGRAM_ALLOWED_USERS in .env file to enable access")
            return False

        is_authorized = user_id in allowed_users
        if not is_authorized:
            logger.warning(f"Unauthorized access attempt from user {user_id}")

        return is_authorized

    async def check_message_security(
        self,
        user_input: str,
        user_id: str,
        allowed_users: list[str],
    ) -> tuple[bool, Optional[str], AuditEventType, AuditSeverity]:
        """
        Comprehensive security check for incoming messages

        Args:
            user_input: User's message
            user_id: User identifier
            allowed_users: List of allowed user IDs

        Returns:
            Tuple of (is_safe, threat_description, audit_event, severity)
        """
        # Check authorization
        if not self.validate_user_authorization(user_id, allowed_users):
            return (
                False,
                "Unauthorized user access attempt",
                AuditEventType.AUTH_FAILURE,
                AuditSeverity.WARNING,
            )

        # Sanitize input
        sanitized_input = self.sanitize_input(user_input)

        # Check for prompt injection
        is_injection, pattern = self.detect_prompt_injection(sanitized_input)
        if is_injection:
            return (
                False,
                f"Prompt injection detected: {pattern}",
                AuditEventType.PROMPT_INJECTION_DETECTED,
                AuditSeverity.CRITICAL,
            )

        # Check for suspicious content
        is_suspicious, pattern = self.detect_suspicious_content(sanitized_input)
        if is_suspicious:
            return (
                False,
                f"Suspicious content detected: {pattern}",
                AuditEventType.SECURITY_ALERT,
                AuditSeverity.WARNING,
            )

        # All checks passed
        return True, None, AuditEventType.MESSAGE_RECEIVED, AuditSeverity.INFO


# Global security layer instance
security_layer = SecurityLayer()
