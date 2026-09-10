"""Camoufox launch helper shared by auth.py and exporter.py."""
import random
from contextlib import asynccontextmanager
from pathlib import Path

from camoufox.async_api import AsyncCamoufox
from loguru import logger


@asynccontextmanager
async def launch_browser(profile_dir: Path, headless: bool = False, download_dir: Path | None = None):
    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Profile directory: {profile_dir}")

    width = random.randint(1280, 1600)
    height = random.randint(800, 1000)

    launch_opts: dict = {
        "persistent_context": True,
        "user_data_dir": str(profile_dir),
        "headless": headless,
        "window": (width, height),
    }
    if download_dir is not None:
        download_dir = Path(download_dir)
        download_dir.mkdir(parents=True, exist_ok=True)
        # Route downloads into our folder so the poll can find them.
        launch_opts["accept_downloads"] = True
        launch_opts["downloads_path"] = str(download_dir)
        logger.info(f"Downloads directory: {download_dir}")

    async with AsyncCamoufox(**launch_opts) as context:
        page = context.pages[0] if context.pages else await context.new_page()
        await page.set_viewport_size({"width": width, "height": height})
        try:
            yield context, context, page
        finally:
            try:
                await context.close()
            except Exception:
                pass
