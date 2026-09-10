import asyncio
import os
import random
from pathlib import Path

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


def _get_password() -> str:
    pw = os.getenv("IG_PASSWORD")
    if not pw:
        raise RuntimeError("IG_PASSWORD not found: set it in .env (see .env.example)")
    return pw


def _locator(page, selector: str):
    s = selector.strip()
    if s.startswith("/") or s.startswith("("):
        return page.locator(f"xpath={s}")
    return page.locator(s)


async def _first_visible(loc):
    try:
        n = await loc.count()
    except Exception:
        return None
    for i in range(n):
        try:
            item = loc.nth(i)
            if await item.is_visible():
                return item
        except Exception:
            continue
    return None


async def realistic_click(page, selector: str, timeout: int = 15000):
    # IG renders duplicate hidden dialogs; .first can grab a hidden node and time out.
    delay = random.uniform(2, 5)
    if random.random() < 0.10:
        delay = random.uniform(1.3, 3.23)
    await asyncio.sleep(delay)
    try:
        loc = _locator(page, selector)
        try:
            total = await loc.count()
        except Exception:
            total = -1
        if total and total > 1:
            for i in range(total):
                try:
                    item = loc.nth(i)
                    if await item.is_visible():
                        try:
                            await item.scroll_into_view_if_needed(timeout=3000)
                        except Exception:
                            pass
                        await item.click(timeout=timeout)
                        return
                except Exception:
                    continue
            logger.warning(f"No visible match / {total} total: {selector[:80]}")
        await loc.first.click(timeout=timeout)
    except Exception as e:
        logger.error(f"Click failed {selector}: {str(e)[:120]}")
        raise


async def wait_visible(page, selector: str, timeout: int = 20000) -> bool:
    loc = _locator(page, selector)
    try:
        await loc.filter(visible=True).first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        import time as _time

        end = _time.monotonic() + timeout / 1000
        while _time.monotonic() < end:
            try:
                if await _first_visible(loc) is not None:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False


async def is_visible_now(page, selector: str) -> bool:
    return await _first_visible(_locator(page, selector)) is not None


async def realistic_type(page, selector: str, text: str, typo_rate: float = 0.03):
    loc = _locator(page, selector)
    await realistic_click(page, selector)
    target = await _first_visible(loc) or loc.first
    for i, char in enumerate(text):
        if random.random() < typo_rate:
            typo = random.choice("abcdefghijklmnopqrstuvwxyz")
            await target.press_sequentially(typo, delay=random.uniform(60, 140))
            await asyncio.sleep(random.uniform(0.15, 0.35))
            await page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.value = (el.value || '').slice(0, -1);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }""",
                selector,
            )
            await asyncio.sleep(random.uniform(0.1, 0.2))
        await target.press_sequentially(char, delay=random.uniform(50, 140))
        await asyncio.sleep(max(0.05, min(random.gauss(0.12, 0.04), 0.25)))
        if random.random() < 0.08 and i < len(text) - 1:
            await asyncio.sleep(random.uniform(0.3, 0.6))


PASSWORD_FIELD_SELECTOR = "div[role='dialog'] input[type='password']"
CONFIRM_BUTTON_XPATH = "//div[@role='dialog']//div[@role='button'][contains(., 'ontinue') or contains(., 'onfirm') or contains(., 'Done')]"


async def confirm_export_password(page, wait_ms: int = 10000) -> bool:
    # True if a password dialog was present and confirmed, False if none appeared.
    if not await wait_visible(page, PASSWORD_FIELD_SELECTOR, timeout=wait_ms):
        logger.info("No password prompt appeared — skipping.")
        return False
    try:
        await page.bring_to_front()
        await page.evaluate("window.focus();")
    except Exception:
        pass
    await realistic_type(page, PASSWORD_FIELD_SELECTOR, _get_password())
    await asyncio.sleep(5)
    if await is_visible_now(page, CONFIRM_BUTTON_XPATH):
        await realistic_click(page, CONFIRM_BUTTON_XPATH)
    else:
        logger.warning("Password typed but Continue/Confirm not visible — continuing anyway.")
    return True


def find_pending_output(base_dir: Path | None = None):
    root = Path(base_dir) if base_dir else Path(__file__).resolve().parent
    output_folder = root / "output"
    if not output_folder.exists() or not any(output_folder.iterdir()):
        return None
    connections_folder = output_folder / "connections" / "followers_and_following"
    if connections_folder.exists():
        logger.info(f"Found leftover data from previous run: {output_folder}")
        return output_folder
    return None
