"""
Quick test script for Google Sheets integration
"""
import asyncio
import sys
from app.automation.sheets_integration import sheets_client
from app.config import settings
from datetime import datetime

# Set UTF-8 encoding for console output
sys.stdout.reconfigure(encoding='utf-8')

async def test_sheets_integration():
    print("=" * 80)
    print("TESTING GOOGLE SHEETS INTEGRATION")
    print("=" * 80)

    # Test authentication
    print("\n1. Testing authentication...")
    auth_success = sheets_client.authenticate()
    if auth_success:
        print("   [SUCCESS] Authentication successful!")
    else:
        print("   [FAILED] Authentication failed")
        return

    # Test Content Trends Sheet
    print("\n2. Testing Content Trends Sheet...")
    print(f"   Sheet ID: {settings.google_sheet_id_trends}")

    test_content_data = [
        {
            'rank': 1,
            'platform': 'X (Twitter)',
            'content_type': 'Tweet',
            'creator': '@TestAccount',
            'headline': 'Test content from O.R.E.I.L.U.S. automation',
            'topic_category': 'Banking',
            'views': '1000',
            'likes': '50',
            'comments': '10',
            'engagement_rate': '6.0%',
            'why_trending': 'Test trending reason',
            'emotional_trigger': 'Curiosity',
            'replication_potential': 'High - Test potential'
        }
    ]

    content_success = sheets_client.write_content_trends(
        test_content_data,
        settings.google_sheet_id_trends
    )

    if content_success:
        print("   [SUCCESS] Content Trends sheet write successful!")
        print(f"   --> Check your sheet: https://docs.google.com/spreadsheets/d/{settings.google_sheet_id_trends}")
    else:
        print("   [FAILED] Content Trends sheet write failed")

    # Test Government Intel Sheet
    print("\n3. Testing Government Intel Sheet...")
    print(f"   Sheet ID: {settings.google_sheet_id_banking}")

    test_intel_data = [
        {
            'rank': 1,
            'source': 'Federal Reserve',
            'institution': 'Federal Reserve',
            'topic': 'Test Topic',
            'what_changed': 'Test change from O.R.E.I.L.U.S. automation',
            'why_matters': 'This is a test entry',
            'impact_consumers': 'Test consumer impact',
            'impact_banks': 'Test bank impact',
            'opportunity_angle': 'Test opportunity',
            'risk_level': 'Low',
            'date_published': datetime.now().strftime("%Y-%m-%d"),
            'source_link': 'https://www.federalreserve.gov'
        }
    ]

    intel_success = sheets_client.write_government_intel(
        test_intel_data,
        settings.google_sheet_id_banking
    )

    if intel_success:
        print("   [SUCCESS] Government Intel sheet write successful!")
        print(f"   --> Check your sheet: https://docs.google.com/spreadsheets/d/{settings.google_sheet_id_banking}")
    else:
        print("   [FAILED] Government Intel sheet write failed")

    print("\n" + "=" * 80)
    if auth_success and content_success and intel_success:
        print("[SUCCESS] ALL TESTS PASSED - Google Sheets integration is working!")
    else:
        print("[FAILED] SOME TESTS FAILED - Check errors above")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_sheets_integration())
