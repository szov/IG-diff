"""Shared config: CLI flags and env vars decide behavior."""
import argparse
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
TARGET_URL = "https://accountscenter.instagram.com/info_and_permissions"

SAVE_BUTTON_XPATH = "//div[@role='button'][contains(., 'Save')]"

DOWNLOAD_DIR = ROOT_DIR / "downloaded_files"
OUTPUT_DIR = ROOT_DIR / "output"
DATA_FILE = ROOT_DIR / "dashboard_data.json"


def default_profile_dir(profile_name: str = "default") -> Path:
    return ROOT_DIR / "profiles" / profile_name


def resolve_profile_dir(explicit: str | None = None, profile_name: str | None = None) -> Path:
    # Precedence: --profile-dir > PROFILE_DIR env > profiles/<name>.
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_dir = os.getenv("PROFILE_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    name = profile_name or os.getenv("PROFILE_NAME", "default")
    return default_profile_dir(name)


def resolve_headless(explicit: bool | None = None) -> bool:
    if explicit is not None:
        return explicit
    return os.getenv("HEADLESS", "false").lower() in ("1", "true", "yes")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="IG-diff")
    p.add_argument("--profile", default=os.getenv("PROFILE_NAME", "default"),
                   help="Profile name under ./profiles/ (default: %(default)s)")
    p.add_argument("--profile-dir", default=os.getenv("PROFILE_DIR"),
                   help="Explicit profile dir (overrides --profile)")
    p.add_argument("--headless", dest="headless", action="store_true",
                   help="Run headless (default headed; use xvfb-run on display-less servers)")
    p.add_argument("--headed", dest="headless", action="store_false",
                   help="Run headed")
    p.set_defaults(headless=None)
    return p


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    ns = build_parser().parse_args(args)
    ns.profile_dir = resolve_profile_dir(ns.profile_dir, ns.profile)
    ns.headless = resolve_headless(ns.headless)
    return ns
