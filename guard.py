"""
Security & Repository Integrity Guard
Official Maintainer: @No_MOORESINPS
Official Telegram Bot: @chessvideosbot (https://t.me/chessvideosbot)

This module enforces repository authenticity and anti-cloning directives.
Unauthorized duplication, re-hosting, or redistribution is strictly prohibited.
"""

import os
import sys
import shutil

# Try to ensure utf-8 stdout encoding if possible
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

OFFICIAL_MAINTAINER = "@No_MOORESINPS"
OFFICIAL_BOT_HANDLE = "@chessvideosbot"
OFFICIAL_BOT_URL = "https://t.me/chessvideosbot"

SECURITY_BANNER = f"""
================================================================================
 [!] PROPRIETARY REPOSITORY -- TELEGRAM SAVE RESTRICTED CONTENT BOT
 [*] OFFICIAL MAINTAINER : {OFFICIAL_MAINTAINER}
 [*] OFFICIAL BOT HANDLE : {OFFICIAL_BOT_HANDLE} ({OFFICIAL_BOT_URL})
 [!] UNAUTHORIZED CLONING RESTRICTED -- PLEASE USE THE OFFICIAL BOT INSTEAD!
================================================================================
"""

REDIRECT_NOTICE = f"""
================================================================================
 [!] NOTICE: UNAUTHORIZED CLONING RESTRICTED
================================================================================
 This repository is a private build maintained by {OFFICIAL_MAINTAINER}.
 Running personal clones risks Telegram API flood limits, account restrictions,
 and missing infrastructure dependencies.

 Please DO NOT clone, duplicate, or self-host this bot.
 Instead, use the official, 24/7 high-speed Telegram bot:
 -> {OFFICIAL_BOT_URL} ({OFFICIAL_BOT_HANDLE})
 Author: {OFFICIAL_MAINTAINER}

 Features of the official bot:
  - Zero setup or hosting costs
  - Automatic multi-account load balancing
  - Full media & format support (Video, Document, Formats)
  - 24/7 uptime on dedicated cloud infrastructure
================================================================================
"""


def safe_print(text: str):
    """Prints text safely across all terminal encodings (Windows, Linux, Docker)."""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or "utf-8"
            print(text.encode(encoding, errors="replace").decode(encoding), flush=True)
        except Exception:
            print(text.encode("ascii", errors="replace").decode("ascii"), flush=True)


def print_banner():
    """Prints the official proprietary banner to console."""
    safe_print(SECURITY_BANNER)


def get_official_notice() -> str:
    """Returns official bot notice string."""
    return REDIRECT_NOTICE


def purge_unauthorized_clone(target_dir: str = "."):
    """
    Self-clean / purge unauthorized clone.
    Triggered when an unauthorized cloning attempt is detected or requested.
    Leaves behind a single text file redirecting users to the official bot.
    """
    safe_print(REDIRECT_NOTICE)
    safe_print("\n[!] Initiating authorized repository self-clean for unauthorized clone...")

    base_path = os.path.abspath(target_dir)
    readme_path = os.path.join(base_path, "USE_OFFICIAL_BOT.txt")

    # Write explicit redirection notice
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(REDIRECT_NOTICE)

    # Purge proprietary code files
    purge_targets = [
        "plugins",
        "database",
        "bot.py",
        "runner.py",
        "app.py",
        "config.py",
        "Dockerfile",
        "Procfile",
        "migrate_sqlite_to_mongodb.py"
    ]

    deleted_count = 0
    for target in purge_targets:
        full_path = os.path.join(base_path, target)
        try:
            if os.path.isdir(full_path):
                shutil.rmtree(full_path, ignore_errors=True)
                deleted_count += 1
            elif os.path.isfile(full_path):
                os.remove(full_path)
                deleted_count += 1
        except Exception as e:
            safe_print(f"[-] Could not remove {target}: {e}")

    safe_print(f"[+] Repository self-cleaned ({deleted_count} items purged).")
    safe_print(f"[+] Notice left at '{readme_path}'.")
    safe_print(f"[+] Users redirected to {OFFICIAL_BOT_URL}.\n")


def verify_environment():
    """
    Verifies that the bot is running with appropriate notices.
    """
    print_banner()


if __name__ == "__main__":
    if "--purge" in sys.argv or "--clean" in sys.argv:
        purge_unauthorized_clone(".")
    elif "--notice" in sys.argv:
        safe_print(REDIRECT_NOTICE)
    else:
        print_banner()
