"""
Script to update database schema for larger user_id fields
"""
import asyncio
from sqlalchemy import text
from app.database import engine

async def update_schema():
    print("Updating database schema...")

    async with engine.begin() as conn:
        # Increase user_id column size in audit_logs
        await conn.execute(text(
            "ALTER TABLE audit_logs ALTER COLUMN user_id TYPE VARCHAR(255)"
        ))
        print("✓ Updated audit_logs.user_id column")

        # Increase user_id column size in conversations
        await conn.execute(text(
            "ALTER TABLE conversations ALTER COLUMN user_id TYPE VARCHAR(255)"
        ))
        print("✓ Updated conversations.user_id column")

    print("\n✓ Database schema updated successfully!")
    print("You can now restart the backend.")

if __name__ == "__main__":
    asyncio.run(update_schema())
