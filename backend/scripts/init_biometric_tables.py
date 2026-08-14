"""
Initialize Biometric Security Tables and Seed Master Profile
Run this script to create all new biometric security tables
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine, Base, AsyncSessionLocal
from app.models import (
    MasterProfile,
    SecurityMode,
    BehavioralBaseline,
    VocabularyFingerprint,
    EmotionalProfile,
    SessionAuthentication,
    MessageMetrics,
    SecurityChallenge,
    DynamicKeyword
)
from datetime import datetime, timezone


async def init_biometric_tables():
    """Create all biometric security tables"""
    print("Creating biometric security tables...")

    async with engine.begin() as conn:
        # Import all models to ensure they're registered
        await conn.run_sync(Base.metadata.create_all)

    print("✓ Tables created successfully")


async def seed_master_profile():
    """Create initial master profile for Anthony Morales"""
    print("\nSeeding master profile...")

    async with AsyncSessionLocal() as session:
        # Check if master profile already exists
        from sqlalchemy import select
        result = await session.execute(select(MasterProfile).where(MasterProfile.id == 1))
        existing_profile = result.scalar_one_or_none()

        if existing_profile:
            print("✓ Master profile already exists:")
            print(f"  - Name: {existing_profile.name}")
            print(f"  - Security Mode: {existing_profile.security_mode.value}")
            print(f"  - Enrolled: {existing_profile.enrollment_started_at}")
            return

        # Create new master profile
        master_profile = MasterProfile(
            name="Anthony Morales",
            telegram_user_id="5171171510",  # Your Telegram ID
            security_mode=SecurityMode.LEARNING,
            enrollment_started_at=datetime.now(timezone.utc)
        )

        session.add(master_profile)
        await session.commit()

        print("✓ Master profile created successfully:")
        print(f"  - ID: {master_profile.id}")
        print(f"  - Name: {master_profile.name}")
        print(f"  - Security Mode: {master_profile.security_mode.value}")
        print(f"  - Telegram ID: {master_profile.telegram_user_id}")


async def verify_tables():
    """Verify all tables were created"""
    print("\nVerifying tables...")
    from sqlalchemy import text

    tables_to_check = [
        "master_profile",
        "behavioral_baseline",
        "vocabulary_fingerprint",
        "emotional_profile",
        "session_authentication",
        "message_metrics",
        "security_challenges",
        "dynamic_keywords"
    ]

    async with engine.begin() as conn:
        for table_name in tables_to_check:
            result = await conn.execute(
                text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}')")
            )
            exists = result.scalar()
            status = "✓" if exists else "✗"
            print(f"  {status} {table_name}")


async def main():
    """Main initialization function"""
    print("=" * 60)
    print("O.R.E.I.L.U.S. Biometric Security Tables Initialization")
    print("=" * 60)

    try:
        # Step 1: Create tables
        await init_biometric_tables()

        # Step 2: Verify tables
        await verify_tables()

        # Step 3: Seed master profile
        await seed_master_profile()

        print("\n" + "=" * 60)
        print("✓ Initialization complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Restart O.R.E.I.L.U.S. service: systemctl restart oreilus")
        print("2. System is now in LEARNING mode (will collect baseline data)")
        print("3. Interact normally for 2-4 weeks to build behavioral baseline")

    except Exception as e:
        print(f"\n✗ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
