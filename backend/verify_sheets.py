"""
Verify Google Sheets access and permissions
"""
import sys
from app.automation.sheets_integration import sheets_client
from app.config import settings

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 80)
print("VERIFYING GOOGLE SHEETS ACCESS")
print("=" * 80)

# Authenticate
print("\n1. Authenticating...")
if not sheets_client.authenticate():
    print("   [FAILED] Authentication failed")
    exit(1)
print("   [SUCCESS] Authenticated")

# Check Content Trends sheet
print("\n2. Checking Content Trends Sheet...")
print(f"   Sheet ID: {settings.google_sheet_id_trends}")
try:
    sheet = sheets_client.open_sheet(settings.google_sheet_id_trends)
    if sheet:
        print(f"   [SUCCESS] Can open sheet: {sheet.title}")
        print(f"   Worksheets in this sheet:")
        for ws in sheet.worksheets():
            print(f"      - {ws.title} ({ws.row_count} rows x {ws.col_count} cols)")
    else:
        print("   [FAILED] Could not open sheet")
        print("\n   POSSIBLE ISSUE: Sheet not shared with service account!")
        print(f"   Service account email: oreilus-automation@oreilus-automation.iam.gserviceaccount.com")
        print("\n   To fix:")
        print("   1. Open the Google Sheet")
        print("   2. Click 'Share' button")
        print("   3. Add: oreilus-automation@oreilus-automation.iam.gserviceaccount.com")
        print("   4. Set permission to 'Editor'")
        print("   5. Click 'Share'")
except Exception as e:
    print(f"   [FAILED] Error accessing sheet: {e}")
    print("\n   This usually means the sheet was NOT shared with the service account.")
    print(f"   Service account email: oreilus-automation@oreilus-automation.iam.gserviceaccount.com")

# Check Government Intel sheet
print("\n3. Checking Government Intel Sheet...")
print(f"   Sheet ID: {settings.google_sheet_id_banking}")
try:
    sheet = sheets_client.open_sheet(settings.google_sheet_id_banking)
    if sheet:
        print(f"   [SUCCESS] Can open sheet: {sheet.title}")
        print(f"   Worksheets in this sheet:")
        for ws in sheet.worksheets():
            print(f"      - {ws.title} ({ws.row_count} rows x {ws.col_count} cols)")
    else:
        print("   [FAILED] Could not open sheet")
        print("\n   POSSIBLE ISSUE: Sheet not shared with service account!")
        print(f"   Service account email: oreilus-automation@oreilus-automation.iam.gserviceaccount.com")
except Exception as e:
    print(f"   [FAILED] Error accessing sheet: {e}")
    print("\n   This usually means the sheet was NOT shared with the service account.")
    print(f"   Service account email: oreilus-automation@oreilus-automation.iam.gserviceaccount.com")

print("\n" + "=" * 80)
