import asyncio
import json
import random
import shutil
import zipfile
from pathlib import Path

from loguru import logger

from igdiff.analyzer import find_differences
from igdiff.browser import launch_browser
from igdiff.config import (
    TARGET_URL,
    SAVE_BUTTON_XPATH,
    DOWNLOAD_DIR,
    OUTPUT_DIR,
    ROOT_DIR,
    parse_args,
    resolve_headless,
    resolve_profile_dir,
)
from igdiff.interactions import realistic_click, confirm_export_password, find_pending_output, wait_visible
from igdiff.log_config import setup_logging

setup_logging()


def analyze_export(folder_path: Path):
    folder = Path(folder_path) / "connections" / "followers_and_following"
    logger.info(f"Analyzing export data in: {folder}")

    followers_path = None
    for name in ["followers_1.json", "followers.json", "followers1.json"]:
        p = folder / name
        if p.exists():
            followers_path = p
            break
    following_path = folder / "following.json"

    if not followers_path or not followers_path.exists():
        logger.warning(f"Followers file not found in {folder}")
        return [], []
    if not following_path.exists():
        logger.warning(f"Following file not found: {following_path}")
        return [], []

    with open(followers_path, "r", encoding="utf-8") as f:
        followers_data = json.load(f)
    with open(following_path, "r", encoding="utf-8") as f:
        following_data = json.load(f)

    not_following_you, you_not_following = find_differences(followers_data, following_data)
    logger.info(f"Analysis complete: {len(not_following_you)} traitors, {len(you_not_following)} fans")
    return not_following_you, you_not_following


async def wait_for_download(folder: Path, timeout: int = 60, ignore: set[str] | None = None):
    ignore = ignore or set()
    for _ in range(timeout):
        zips = [z for z in folder.glob("*.zip") if z.name not in ignore]
        if zips:
            return max(zips, key=lambda z: z.stat().st_mtime)
        await asyncio.sleep(1)
    return None


DOWNLOAD_BUTTON_XPATH = "//div[@role='dialog']//div[@role='button'][@tabindex='0'][.//span[text()='Download']]"


async def download_ready_export(page, download_dir: Path, max_retries: int = 5):
    # First Download (row) -> swipe animation / new dialog -> second Download
    # (same label) -> password prompt (sometimes skipped) -> file download.
    logger.info("Downloading existing export...")
    sleep_time = random.uniform(200, 300)

    for attempt in range(max_retries):
        try:
            before = {z.name for z in download_dir.glob("*.zip")}
            logger.info(f"Clicking download #1 (Attempt {attempt + 1})...")
            await realistic_click(page, DOWNLOAD_BUTTON_XPATH)

            await asyncio.sleep(3)
            logger.info("Waiting for download #2 dialog...")
            if not await wait_visible(page, DOWNLOAD_BUTTON_XPATH, timeout=20000):
                logger.warning("Download #2 never became visible — reloading.")
                await page.reload()
                await asyncio.sleep(sleep_time)
                continue

            logger.info("Clicking download #2...")
            await realistic_click(page, DOWNLOAD_BUTTON_XPATH)

            had_password = await confirm_export_password(page, wait_ms=10000)
            logger.info(f"Password prompt {'confirmed' if had_password else 'skipped (none shown)'}.")

            if had_password:
                logger.info("Waiting for browser download event (120s)...")
                try:
                    async with page.expect_download(timeout=120000) as dl_info:
                        download = await dl_info.value
                    dest = download_dir / (download.suggested_filename or "instagram_export.zip")
                    await download.save_as(dest)
                    logger.info(f"Download saved: {dest} ({dest.stat().st_size} bytes)")
                except Exception as e:
                    logger.warning(f"No download event captured: {str(e)[:150]} — falling back to folder poll.")

            logger.info("Waiting for file generation...")
            zip_file = await wait_for_download(download_dir, timeout=60, ignore=before)
            if not zip_file:
                logger.warning(f"No zip file found (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(sleep_time)
                await page.reload()
                continue

            logger.info("Extracting zip file...")
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_file) as z:
                z.extractall(OUTPUT_DIR)
            zip_file.unlink()

            logger.info("Closing dialogs...")
            await page.reload()
            try:
                await realistic_click(page, "//div[@role='dialog']//div[@role='button'][@tabindex='0'][.//span[text()='Cancel']]")
                await realistic_click(page, "//div[@role='button'][contains(.,'Yes')]")
            except Exception:
                pass
            return OUTPUT_DIR
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(sleep_time)
                try:
                    await page.reload()
                except Exception:
                    pass
            else:
                return None
    return None


async def request_new_export(page, download_dir: Path):
    logger.info("Creating new export request...")
    steps = [
        ("Create export", "//div[@role='dialog']//div[@role='button'][contains(., 'Create export')]"),
        ("Select device", "//div[@role='dialog']//div[@role='button'][contains(., 'device')]"),
        ("Select information", "//div[@role='dialog']//div[@role='button'][contains(., 'information')]"),
    ]
    for step_name, selector in steps:
        try:
            logger.info(f"Step: {step_name}...")
            await realistic_click(page, selector)
        except Exception:
            return False

    logger.info("Configuring options...")
    while True:
        try:
            await realistic_click(page, "//div[@role='dialog']//div[@role='button'][contains(., 'Clear')]")
        except Exception:
            break

    await realistic_click(page, "//div[@role='group']//label[contains(., 'following')]")
    await realistic_click(page, SAVE_BUTTON_XPATH)
    await realistic_click(page, "//div[@role='dialog']//div[@role='button'][contains(., 'range')]")
    await realistic_click(page, "//div[@role='radiogroup']//label[contains(., 'All')]")
    await realistic_click(page, SAVE_BUTTON_XPATH)
    await realistic_click(page, "//div[@role='dialog']//div[@role='button'][contains(., 'Format')]")
    await realistic_click(page, "//div[@role='radiogroup']//label[contains(., 'JSON')]")
    await realistic_click(page, SAVE_BUTTON_XPATH)
    await realistic_click(page, "//div[@role='dialog']//div[@role='button'][contains(., 'quality')]")
    await realistic_click(page, "//div[@role='radiogroup']//label[contains(., 'Higher')]")
    await realistic_click(page, SAVE_BUTTON_XPATH)

    logger.info("Finalizing request...")
    await realistic_click(page, "//div[@role='button'][contains(., 'Start')]")
    try:
        await confirm_export_password(page)
    except Exception:
        pass

    logger.info("Waiting for download to be ready...")
    return await download_ready_export(page, download_dir)


async def open_export_page(page) -> bool:
    logger.info("Loading Instagram...")
    await page.goto(TARGET_URL)
    await page.wait_for_timeout(2000)
    if "login" in page.url:
        logger.error("Not logged in!")
        return False
    logger.info("Navigating to Export menu...")
    await realistic_click(page, "//main//div[@role='button'][contains(@aria-label, 'Export')]")
    return True


async def run_export_flow(profile_dir: Path | None = None, headless: bool = False):
    profile_dir = resolve_profile_dir(str(profile_dir) if profile_dir else None)
    headless = resolve_headless(headless)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Starting export run")
    result_data = ([], [])
    extract_path = None

    async with launch_browser(profile_dir, headless=headless, download_dir=DOWNLOAD_DIR) as (_, _ctx, page):
        if not await open_export_page(page):
            logger.error("Error: Not logged in.")
            return result_data

        logger.info("Checking for existing exports...")
        found = False
        for xp in [
            "//div[@role='tabpanel']//h2[contains(.,'ownload')]",
            "//div[@role='tabpanel']//h2[contains(.,'equested')]",
        ]:
            try:
                await page.locator(f"xpath={xp}").first.wait_for(timeout=8000)
                found = True
                break
            except Exception:
                continue

        if found:
            logger.info("Existing export found")
            extract_path = await download_ready_export(page, DOWNLOAD_DIR)
        else:
            logger.info("No existing export found, checking leftover data...")
            leftover_path = find_pending_output(ROOT_DIR)
            extract_path = leftover_path if leftover_path else await request_new_export(page, DOWNLOAD_DIR)

        if extract_path:
            result_data = analyze_export(extract_path)
            logger.info("Cleaning up files...")
            try:
                for item in Path(extract_path).iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
            except Exception:
                pass
        else:
            logger.warning("Failed: No data found.")

    return result_data


if __name__ == "__main__":
    args = parse_args()
    print(f"profile={args.profile_dir} headless={args.headless}")
    asyncio.run(run_export_flow(args.profile_dir, args.headless))
