"""
Test social media authentication
Run this to verify Instagram, Facebook, and LinkedIn login works
"""
import asyncio
import sys
from loguru import logger

# Add app directory to path
sys.path.insert(0, 'C:/Users/Victoria/oreilus/backend')

from app.automation.scrapers.instagram_scraper import instagram_scraper
from app.automation.scrapers.facebook_scraper import facebook_scraper
from app.automation.scrapers.linkedin_scraper import linkedin_scraper


async def test_instagram():
    """Test Instagram authentication"""
    logger.info("=" * 60)
    logger.info("Testing Instagram Authentication")
    logger.info("=" * 60)

    try:
        # Try to get trending posts with a simple keyword
        posts = await instagram_scraper.get_trending_posts(['banking'], limit=3)

        if posts:
            logger.success(f"✓ Instagram authentication successful! Found {len(posts)} posts")
            for post in posts[:2]:  # Show first 2
                logger.info(f"  - {post['platform']}: {post['headline'][:50]}...")
            return True
        else:
            logger.warning("Instagram returned empty results (may be using mock data)")
            return False

    except Exception as e:
        logger.error(f"✗ Instagram test failed: {e}")
        return False


async def test_facebook():
    """Test Facebook authentication"""
    logger.info("=" * 60)
    logger.info("Testing Facebook Authentication")
    logger.info("=" * 60)

    try:
        posts = await facebook_scraper.get_trending_posts(['banking'], limit=3)

        if posts:
            logger.success(f"✓ Facebook authentication successful! Found {len(posts)} posts")
            for post in posts[:2]:
                logger.info(f"  - {post['platform']}: {post['headline'][:50]}...")
            return True
        else:
            logger.warning("Facebook returned empty results (may be using mock data)")
            return False

    except Exception as e:
        logger.error(f"✗ Facebook test failed: {e}")
        return False


async def test_linkedin():
    """Test LinkedIn authentication"""
    logger.info("=" * 60)
    logger.info("Testing LinkedIn Authentication")
    logger.info("=" * 60)

    try:
        posts = await linkedin_scraper.get_trending_posts(['banking'], limit=3)

        if posts:
            logger.success(f"✓ LinkedIn authentication successful! Found {len(posts)} posts")
            for post in posts[:2]:
                logger.info(f"  - {post['platform']}: {post['headline'][:50]}...")
            return True
        else:
            logger.warning("LinkedIn returned empty results (may be using mock data)")
            return False

    except Exception as e:
        logger.error(f"✗ LinkedIn test failed: {e}")
        return False


async def main():
    """Run all authentication tests"""
    logger.info("Starting Social Media Authentication Tests")
    logger.info("This will test Instagram, Facebook, and LinkedIn logins")
    logger.info("")

    results = {
        'instagram': await test_instagram(),
        'facebook': await test_facebook(),
        'linkedin': await test_linkedin()
    }

    logger.info("")
    logger.info("=" * 60)
    logger.info("AUTHENTICATION TEST RESULTS")
    logger.info("=" * 60)

    for platform, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL (using mock data)"
        logger.info(f"{platform.capitalize():15} {status}")

    logger.info("")

    passed = sum(results.values())
    total = len(results)

    if passed == total:
        logger.success(f"All {total} platforms authenticated successfully!")
    elif passed > 0:
        logger.warning(f"{passed}/{total} platforms authenticated. Some are using mock data.")
    else:
        logger.error("All platforms failed to authenticate. Check credentials in .env file")

    logger.info("")
    logger.info("Note: If authentication fails, scrapers will automatically fall back to mock data.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
