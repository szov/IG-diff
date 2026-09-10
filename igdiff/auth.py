import asyncio

from loguru import logger

from igdiff.browser import launch_browser
from igdiff.config import parse_args
from igdiff.log_config import setup_logging

setup_logging()


async def save_login_session(profile_dir, headless: bool = False):
    logger.info("Opening Instagram login page...")
    async with launch_browser(profile_dir, headless=headless) as (_, _ctx, page):
        await page.goto("https://www.instagram.com/accounts/login/")
        print("\n" + "=" * 50)
        print("MANUAL LOGIN REQUIRED")
        print("=" * 50)
        print("1. Log in to Instagram manually")
        print("2. Complete 2FA if prompted")
        print("3. Wait for home feed to load")
        print("4. Press Enter here to save session")
        print("=" * 50 + "\n")
        logger.info("Waiting for login...")
        while True:
            try:
                home = await page.query_selector("svg[aria-label='Home']")
                logo = await page.query_selector("svg[aria-label='Instagram']")
                if home or logo:
                    logger.info("Login detected, home feed loaded")
                    print("\nPress Enter to save session and close...")
                    input()
                    logger.info("Session saved, closing browser")
                    break
            except Exception:
                pass
            await asyncio.sleep(2)


if __name__ == "__main__":
    args = parse_args()
    print(f"profile={args.profile_dir} headless={args.headless}")
    asyncio.run(save_login_session(args.profile_dir, args.headless))
