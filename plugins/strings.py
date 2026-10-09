from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

HELP_MAIN_TXT = """📖 **Aditya's Bot — Help Center**

Welcome! Select a category below to explore guides, link syntax, and customization settings:

• **📥 Download Guide** — Public/private posts & batch ranges
• **🏷️ Cleaner & Renamer** — Auto-ad removal & custom prefixes
• **⚙️ Settings & Formats** — Video/Doc modes, Silent, Saved Messages
• **🌐 Web Downloader** — YouTube, Reels, X, and direct links
• **📌 Commands List** — Quick command cheat sheet
"""

HELP_DOWNLOAD_TXT = """📥 **How to Download Telegram Content**

**1. Public Channels:**
Send any post link directly:
`https://t.me/channel_name/1234`

**2. Private Channels / Groups:**
1. Connect your account first using `/login`.
2. If you haven't joined the chat yet, send its invite link.
3. Then send the private post link:
`https://t.me/c/1234567890/456`

**3. Batch Downloads (Multiple Files):**
Send a post range separated by a hyphen:
`https://t.me/channel_name/100-120`
`https://t.me/c/1234567890/50-75`

**4. Forum Topics & Course Threads:**
Transfer all files in an entire topic thread:
`/topic https://t.me/c/3641059847/1321/1413`
Or send a topic range:
`https://t.me/c/3641059847/1321/1300-1450`
• Automatically standardizes sequence: `[300] Subject - Lecture - Part 1.mp4`
• Generates a full Verification & Audit Checklist!

💡 *Tip: If a batch is interrupted by internet drop or restart, send `/resume` to continue from the exact last file!*
"""

HELP_CLEANER_TXT = """🏷️ **Filename Cleaner & Renamer**

🧹 **Auto-Cleaner (Always Active):**
Automatically cleans **all** files (PDF, ZIP, APK, MP4, MP3, etc.):
• Strips: `cracked by...`, `extracted by...`, `downloaded from...`, `uploaded by...`, `shared by...`
• Strips: `@channel_usernames` and promo tags
• Strips: Web links (`https://...`, `t.me/...`, `www...`)
• Cleans: Messy underscores and repeat characters

**Custom Renaming Commands:**
• `/set_prefix <text>` — Add custom text at the start of all files
  *(Example: `/set_prefix [Course]`)*
• `/del_prefix` — Remove your custom prefix
• `/replace <words>` — Add extra words/ads to strip (comma-separated)
• `/del_replace` — Clear custom removal words
"""

HELP_SETTINGS_TXT = """⚙️ **Delivery & Format Settings**

• `/mode` — Toggle between:
  - **Video Mode** *(streamable inline player)*
  - **Document Mode** *(uncompressed raw file, preserves 100% original quality)*

• `/silent` — Toggle silent delivery:
  Upload files quietly without notification sounds.

• `/to_saved` — Toggle destination:
  Send directly to **Saved Messages** or the **Bot Chat**.

• `/set_thumb` — Reply to any image to set custom thumbnail
• `/see_thumb` & `/del_thumb` — View or delete custom thumbnail

• `/set_caption <text>` — Custom caption with dynamic tags:
  `{filename}`, `{size}`, `{caption}`
• `/see_caption` & `/del_caption` — View or reset caption
"""

HELP_WEB_TXT = """🌐 **External Web Downloader (yt-dlp)**

Download videos and media from external websites directly into Telegram!

**Supported Platforms:**
• **YouTube** — Full videos and Shorts
• **Instagram** — Reels, Posts, and Carousels
• **Twitter / X** — Video tweets
• **Direct Media Links** — MP4, MKV, MP3, etc.

**How to Use:**
Simply paste any supported web link into the chat!
"""

HELP_COMMANDS_TXT = """📌 **Quick Command Cheat Sheet**

`/start` — Check bot status & welcome
`/help` — Open this interactive menu
`/status` — View storage & settings dashboard
`/login` — Connect your Telegram user account
`/logout` — Disconnect your session
`/cancel` — Cancel active download task
`/clear` — Clear chat history from both sides in one click
`/reset` — Reset all custom settings & preferences to default
`/resume` — Resume interrupted batch
`/topic` — Crawl & transfer entire forum topic with audit report
`/mode` — Toggle Video vs. Document
`/silent` — Toggle silent notifications
`/to_saved` — Toggle Saved Messages routing
`/set_prefix` — Set custom filename prefix
`/del_prefix` — Delete custom filename prefix
`/replace` — Add custom words to strip
`/del_replace` — Clear custom removal words
`/set_thumb` — Set custom thumbnail (reply to photo)
`/see_thumb` — View current custom thumbnail
`/del_thumb` — Remove custom thumbnail
`/set_caption` — Set custom caption template
`/see_caption` — View current caption template
`/del_caption` — Reset to original caption
"""

def get_help_main_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Download Guide", callback_data="help_download"),
            InlineKeyboardButton("🏷️ Cleaner & Renamer", callback_data="help_cleaner")
        ],
        [
            InlineKeyboardButton("⚙️ Settings & Formats", callback_data="help_settings"),
            InlineKeyboardButton("🌐 Web Downloader", callback_data="help_web")
        ],
        [
            InlineKeyboardButton("📌 All Commands List", callback_data="help_commands")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data="help_close")
        ]
    ])

def get_help_back_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 Back to Help Menu", callback_data="help_main"),
            InlineKeyboardButton("❌ Close", callback_data="help_close")
        ]
    ])
