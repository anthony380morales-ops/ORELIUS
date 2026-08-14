"""
Telegram Bot for O.R.E.I.L.U.S.
Enables mobile chat access via Telegram
"""
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ..config import settings
from ..database import AsyncSessionLocal
from ..core import oreilus_engine
from ..models.conversation import MessageSource
from ..utils.logger import logger
from ..automation.scheduler import automation_scheduler
from ..automation.content_scanner import run_content_scan
from ..automation.government_intel import run_government_scan


class OreilusTelegramBot:
    """Telegram bot for O.R.E.I.L.U.S."""

    def __init__(self):
        self.token = settings.telegram_bot_token
        self.allowed_users = settings.allowed_telegram_users
        self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = str(update.effective_user.id)

        # Check authorization
        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text(
                "⛔ Unauthorized access. This bot is restricted to authorized users only."
            )
            logger.warning(f"Unauthorized Telegram access attempt: {user_id}")
            return

        welcome_message = """
🤖 **O.R.E.I.L.U.S. ACTIVATED**

_Optimized Revenue Engine & Intelligent Logistics Unified System_

Good to see you, Master. I am operational and at your service.

**System Commands:**
/start - Initialize system
/status - System status check
/help - Full command reference

**Automation Commands:**
/automations - View scheduled tasks
/automation_status - Check scheduler
/trigger_content - Run content scanner
/trigger_intel - Run intel scanner
/dashboard - Dashboard access info

You may also send me direct messages for strategic consultation, business intelligence, or systems optimization.

Awaiting your command.
"""
        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        logger.info(f"Telegram bot started for user {user_id}")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = str(update.effective_user.id)

        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            return

        async with AsyncSessionLocal() as db:
            # Get system status
            status = await oreilus_engine.validate_system()

            status_message = f"""
🟢 **SYSTEM STATUS: {status['status'].upper()}**

**Core Components:**
• Claude API: {status['components'].get('claude_api', 'unknown')}
• Security Layer: {status['components'].get('security_layer', 'unknown')}
• Memory Manager: {status['components'].get('memory_manager', 'unknown')}

All systems nominal. Ready for operation.
"""
            await update.message.reply_text(status_message, parse_mode="Markdown")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
📚 **O.R.E.I.L.U.S. COMMAND REFERENCE**

**System Commands:**
/start - Initialize system connection
/status - Check system health
/help - Display this reference

**Automation Commands:**
/automations - View all scheduled automations
/automation_status - Check automation system status
/trigger_content - Run Content Trend Scanner now
/trigger_intel - Run Government Intel Scanner now
/dashboard - Get dashboard access information

**Direct Messaging:**
Simply send me a message for:
• Strategic business consultation
• Market intelligence analysis
• Systems optimization recommendations
• Security advisory
• LUCIUS, GREECE, ION Systems support

I am designed to serve your business empire with data-driven insights and strategic guidance.
"""
        await update.message.reply_text(help_message, parse_mode="Markdown")

    async def automations_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /automations command - Show scheduled automations"""
        user_id = str(update.effective_user.id)

        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            return

        try:
            jobs = automation_scheduler.get_jobs()

            if not jobs:
                await update.message.reply_text(
                    "⚠️ **No automations scheduled**\n\n"
                    "The automation system may not be running properly. "
                    "Please check the backend logs.",
                    parse_mode="Markdown"
                )
                return

            message = "🤖 **SCHEDULED AUTOMATIONS**\n\n"

            for job in jobs:
                next_run = job.next_run_time.strftime("%Y-%m-%d %I:%M %p %Z") if job.next_run_time else "Not scheduled"
                message += f"**{job.name}**\n"
                message += f"• ID: `{job.id}`\n"
                message += f"• Next Run: {next_run}\n"
                message += f"• Trigger: {str(job.trigger)}\n\n"

            message += "\n_Use /trigger_content or /trigger_intel to run them manually._"

            await update.message.reply_text(message, parse_mode="Markdown")
            logger.info(f"Automation list requested by user {user_id}")

        except Exception as e:
            logger.error(f"Failed to get automations: {e}")
            await update.message.reply_text(
                f"⚠️ **Error retrieving automations**\n\n{str(e)}",
                parse_mode="Markdown"
            )

    async def automation_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /automation_status command - Check automation system status"""
        user_id = str(update.effective_user.id)

        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            return

        try:
            jobs = automation_scheduler.get_jobs()
            scheduler_running = automation_scheduler.scheduler.running if automation_scheduler.scheduler else False

            status_icon = "🟢" if scheduler_running else "🔴"
            status_text = "RUNNING" if scheduler_running else "STOPPED"

            message = f"""
{status_icon} **AUTOMATION SYSTEM STATUS: {status_text}**

**Scheduler Information:**
• Status: {status_text}
• Timezone: {str(automation_scheduler.timezone)}
• Jobs Scheduled: {len(jobs)}

**Scheduled Tasks:**
"""
            if jobs:
                for job in jobs:
                    next_run = job.next_run_time.strftime("%Y-%m-%d %I:%M %p %Z") if job.next_run_time else "Not scheduled"
                    message += f"\n• **{job.name}**\n"
                    message += f"  Next run: {next_run}\n"
            else:
                message += "\n⚠️ No jobs scheduled\n"

            if not scheduler_running:
                message += "\n\n⚠️ **WARNING**: Automation scheduler is not running. Please restart the backend service."

            await update.message.reply_text(message, parse_mode="Markdown")
            logger.info(f"Automation status requested by user {user_id}")

        except Exception as e:
            logger.error(f"Failed to get automation status: {e}")
            await update.message.reply_text(
                f"⚠️ **Error checking automation status**\n\n{str(e)}",
                parse_mode="Markdown"
            )

    async def trigger_content_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trigger_content command - Manually run Content Trend Scanner"""
        user_id = str(update.effective_user.id)

        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            return

        await update.message.reply_text(
            "🔄 **Starting Content Trend Scanner...**\n\n"
            "This may take a few minutes. I'll notify you when complete.",
            parse_mode="Markdown"
        )

        try:
            logger.info(f"Manual Content Trend Scanner triggered by user {user_id}")
            result = await run_content_scan()

            success_icon = "✅" if result.get("success") else "⚠️"
            message = f"{success_icon} **Content Trend Scanner Complete**\n\n"

            if result.get("success"):
                message += f"• Trends Found: {result.get('trends_found', 0)}\n"
                message += f"• Sheet Updated: {result.get('sheet_updated', False)}\n"
                message += f"• Timestamp: {result.get('timestamp', 'N/A')}\n"
            else:
                message += f"Error: {result.get('error', 'Unknown error')}\n"

            await update.message.reply_text(message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Failed to trigger Content Trend Scanner: {e}")
            await update.message.reply_text(
                f"⚠️ **Error running scanner**\n\n{str(e)}",
                parse_mode="Markdown"
            )

    async def trigger_intel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /trigger_intel command - Manually run Government Intel Scanner"""
        user_id = str(update.effective_user.id)

        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            return

        await update.message.reply_text(
            "🔄 **Starting Government Intel Scanner...**\n\n"
            "This may take a few minutes. I'll notify you when complete.",
            parse_mode="Markdown"
        )

        try:
            logger.info(f"Manual Government Intel Scanner triggered by user {user_id}")
            result = await run_government_scan()

            success_icon = "✅" if result.get("success") else "⚠️"
            message = f"{success_icon} **Government Intel Scanner Complete**\n\n"

            if result.get("success"):
                message += f"• Updates Found: {result.get('updates_found', 0)}\n"
                message += f"• Sheet Updated: {result.get('sheet_updated', False)}\n"
                message += f"• Timestamp: {result.get('timestamp', 'N/A')}\n"
            else:
                message += f"Error: {result.get('error', 'Unknown error')}\n"

            await update.message.reply_text(message, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Failed to trigger Government Intel Scanner: {e}")
            await update.message.reply_text(
                f"⚠️ **Error running scanner**\n\n{str(e)}",
                parse_mode="Markdown"
            )

    async def dashboard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /dashboard command - Provide dashboard access information"""
        user_id = str(update.effective_user.id)

        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            return

        message = f"""
🖥️ **O.R.E.I.L.U.S. DASHBOARD ACCESS**

**Dashboard URL:**
`{settings.frontend_url}`

**Backend API:**
`{settings.backend_url}`

**Access Information:**
The dashboard provides full control over:
• Automation scheduling
• System configuration
• Google Sheets integration
• Live chat interface
• Security settings

**Note:** The Telegram bot provides command-line access to key functions, but the dashboard offers the complete interface for system management.

**Quick Commands:**
/automations - View scheduled tasks
/automation_status - Check scheduler status
/trigger_content - Run content scanner
/trigger_intel - Run intel scanner
"""

        await update.message.reply_text(message, parse_mode="Markdown")
        logger.info(f"Dashboard info requested by user {user_id}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming text messages"""
        user_id = str(update.effective_user.id)
        user_message = update.message.text

        # Check authorization
        if self.allowed_users and int(user_id) not in self.allowed_users:
            await update.message.reply_text("⛔ Unauthorized")
            logger.warning(f"Unauthorized Telegram message from {user_id}")
            return

        logger.info(f"Telegram message from {user_id}: {user_message[:50]}...")

        # Show typing indicator
        await update.message.chat.send_action("typing")

        try:
            async with AsyncSessionLocal() as db:
                # Process message with O.R.E.I.L.U.S.
                response = await oreilus_engine.process_message(
                    db=db,
                    user_id=user_id,
                    user_message=user_message,
                    source=MessageSource.TELEGRAM,
                    stream=False,
                )

                # Send response
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

        # Add system command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("help", self.help_command))

        # Add automation command handlers
        self.application.add_handler(CommandHandler("automations", self.automations_command))
        self.application.add_handler(CommandHandler("automation_status", self.automation_status_command))
        self.application.add_handler(CommandHandler("trigger_content", self.trigger_content_command))
        self.application.add_handler(CommandHandler("trigger_intel", self.trigger_intel_command))
        self.application.add_handler(CommandHandler("dashboard", self.dashboard_command))

        # Add message handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Error handler
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
