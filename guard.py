"""
Repository Integrity & Maintainer Notice
Official Maintainer: @No_MOORESINPS
Official Telegram Bot: @chessvideosbot (https://t.me/chessvideosbot)
"""

OFFICIAL_MAINTAINER = "@No_MOORESINPS"
OFFICIAL_BOT_HANDLE = "@chessvideosbot"
OFFICIAL_BOT_URL = "https://t.me/chessvideosbot"

SECURITY_BANNER = f"""
================================================================================
 [!] TELEGRAM SAVE RESTRICTED CONTENT BOT
 [*] OFFICIAL MAINTAINER : {OFFICIAL_MAINTAINER}
 [*] OFFICIAL BOT HANDLE : {OFFICIAL_BOT_HANDLE} ({OFFICIAL_BOT_URL})
================================================================================
"""

def print_banner():
    """Prints the official maintainer banner to console."""
    try:
        print(SECURITY_BANNER, flush=True)
    except Exception:
        pass

def verify_environment():
    """Verifies that the bot is running with appropriate notices."""
    print_banner()

if __name__ == "__main__":
    print_banner()
