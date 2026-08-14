"""
Generate JWT Token for Anthony Morales
Run this script to get an access token for API authentication
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.auth import create_access_token, create_refresh_token, create_api_key_token
from app.config import settings
from datetime import timedelta


def main():
    """Generate tokens for Anthony Morales"""
    print("=" * 60)
    print("O.R.E.I.L.U.S. Token Generator")
    print("=" * 60)

    # Get user ID from settings
    allowed_users = settings.telegram_allowed_users.split(",") if settings.telegram_allowed_users else []

    if not allowed_users:
        print("\n✗ ERROR: No allowed users configured in .env")
        print("Please set TELEGRAM_ALLOWED_USERS in /opt/oreilus/backend/.env")
        sys.exit(1)

    user_id = allowed_users[0]  # Anthony's Telegram ID
    print(f"\nGenerating tokens for User ID: {user_id}")

    # Generate access token (1 hour)
    print("\n1. Access Token (expires in 1 hour):")
    access_token = create_access_token(user_id)
    print(f"   {access_token}")

    # Generate refresh token (30 days)
    print("\n2. Refresh Token (expires in 30 days):")
    refresh_token = create_refresh_token(user_id)
    print(f"   {refresh_token}")

    # Generate long-lived API key (1 year)
    print("\n3. API Key for Automation (expires in 1 year):")
    api_key = create_api_key_token("automation_key", expires_days=365)
    print(f"   {api_key}")

    print("\n" + "=" * 60)
    print("How to Use These Tokens:")
    print("=" * 60)

    print("\n📱 For API Requests:")
    print("   curl -H \"Authorization: Bearer YOUR_ACCESS_TOKEN\" \\")
    print(f"        http://146.190.162.19:8000/api/chat")

    print("\n🤖 For Automation/Scripts:")
    print("   Use the API Key (long-lived) in your automation scripts")

    print("\n🔄 To Refresh Access Token:")
    print("   POST to /api/auth/refresh with your refresh_token")

    print("\n💡 Pro Tip:")
    print("   Store your refresh token securely and use it to get new access tokens")
    print("   Access tokens expire in 1 hour, refresh tokens last 30 days")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
