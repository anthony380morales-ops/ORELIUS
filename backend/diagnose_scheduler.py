#!/usr/bin/env python3
"""
Diagnostic script to check O.R.E.I.L.U.S. automation scheduler status
Run this on your VPS to diagnose why automations aren't running

Usage:
    python3 diagnose_scheduler.py
    OR
    ./diagnose_scheduler.py (after chmod +x)
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.automation.scheduler import automation_scheduler
from app.config import settings
from loguru import logger


async def diagnose():
    """Run comprehensive scheduler diagnostics"""

    print("=" * 60)
    print("O.R.E.I.L.U.S. AUTOMATION SCHEDULER DIAGNOSTICS")
    print("=" * 60)
    print()

    # Check 1: Environment Configuration
    print("1. ENVIRONMENT CONFIGURATION")
    print(f"   Environment: {settings.environment}")
    print(f"   Backend URL: {settings.backend_url}")
    print(f"   Claude API Key: {'✓ Set' if settings.claude_api_key else '✗ Missing'}")
    print(f"   Google Sheets Creds: {'✓ Set' if settings.google_sheets_credentials_file else '✗ Missing'}")
    print()

    # Check 2: Scheduler Status
    print("2. SCHEDULER STATUS")
    try:
        if automation_scheduler.scheduler:
            print(f"   Scheduler Object: ✓ Created")
            print(f"   Scheduler Running: {automation_scheduler.scheduler.running}")
            print(f"   Timezone: {automation_scheduler.timezone}")
        else:
            print(f"   Scheduler Object: ✗ Not initialized")
            print("   Attempting to initialize...")
            automation_scheduler.setup()
            automation_scheduler.schedule_daily_tasks()
            print(f"   Scheduler initialized: ✓")
    except Exception as e:
        print(f"   Scheduler Error: ✗ {str(e)}")
    print()

    # Check 3: Scheduled Jobs
    print("3. SCHEDULED JOBS")
    try:
        jobs = automation_scheduler.get_jobs()
        if jobs:
            print(f"   Jobs Found: {len(jobs)}")
            for job in jobs:
                print(f"\n   Job: {job.name}")
                print(f"   - ID: {job.id}")
                print(f"   - Next Run: {job.next_run_time}")
                print(f"   - Trigger: {job.trigger}")
        else:
            print(f"   Jobs Found: 0")
            print(f"   ⚠️  WARNING: No jobs scheduled!")
            print(f"   Attempting to schedule jobs...")
            automation_scheduler.schedule_daily_tasks()
            jobs = automation_scheduler.get_jobs()
            print(f"   Jobs after scheduling: {len(jobs)}")
    except Exception as e:
        print(f"   Jobs Error: ✗ {str(e)}")
    print()

    # Check 4: Try Starting Scheduler
    print("4. SCHEDULER START TEST")
    try:
        if not automation_scheduler.scheduler or not automation_scheduler.scheduler.running:
            print("   Attempting to start scheduler...")
            automation_scheduler.start()
            print("   Scheduler started: ✓")

            # Wait a moment and check again
            await asyncio.sleep(2)
            jobs = automation_scheduler.get_jobs()
            print(f"   Jobs after start: {len(jobs)}")

            if jobs:
                print("\n   ✓ SUCCESS: Scheduler is running with scheduled jobs")
                for job in jobs:
                    print(f"   - {job.name}: Next run at {job.next_run_time}")
            else:
                print("\n   ✗ PROBLEM: Scheduler started but no jobs scheduled")
        else:
            print("   Scheduler already running: ✓")
            jobs = automation_scheduler.get_jobs()
            print(f"   Active jobs: {len(jobs)}")
    except Exception as e:
        print(f"   Start Error: ✗ {str(e)}")
        import traceback
        print("\n   Full traceback:")
        print(traceback.format_exc())
    print()

    # Check 5: Dependencies
    print("5. DEPENDENCY CHECK")
    try:
        from app.automation.content_scanner import run_content_scan
        print("   content_scanner: ✓")
    except Exception as e:
        print(f"   content_scanner: ✗ {str(e)}")

    try:
        from app.automation.government_intel import run_government_scan
        print("   government_intel: ✓")
    except Exception as e:
        print(f"   government_intel: ✗ {str(e)}")

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        print("   apscheduler: ✓")
    except Exception as e:
        print(f"   apscheduler: ✗ {str(e)}")
    print()

    # Check 6: Manual Trigger Test
    print("6. MANUAL TRIGGER TEST")
    try:
        print("   Testing Content Scanner import...")
        from app.automation.content_scanner import run_content_scan
        print("   ✓ Content Scanner imported successfully")
        print("   Note: Not running scan to avoid API usage")
    except Exception as e:
        print(f"   ✗ Content Scanner error: {str(e)}")
    print()

    # Summary
    print("=" * 60)
    print("DIAGNOSIS COMPLETE")
    print("=" * 60)
    print()

    if automation_scheduler.scheduler and automation_scheduler.scheduler.running:
        jobs = automation_scheduler.get_jobs()
        if jobs:
            print("✅ STATUS: Scheduler is WORKING correctly")
            print(f"   {len(jobs)} jobs scheduled")
            print("\nNext scheduled runs:")
            for job in sorted(jobs, key=lambda j: j.next_run_time or ""):
                print(f"   - {job.name}: {job.next_run_time}")
        else:
            print("⚠️  STATUS: Scheduler RUNNING but NO JOBS scheduled")
            print("   Action: Check scheduler.py schedule_daily_tasks() method")
    else:
        print("❌ STATUS: Scheduler NOT RUNNING")
        print("   Action: Check logs for errors during startup")

    print()
    print("To test on VPS:")
    print("   1. SSH to VPS")
    print("   2. cd /root/oreilus/backend")
    print("   3. python diagnose_scheduler.py")
    print()


if __name__ == "__main__":
    asyncio.run(diagnose())
