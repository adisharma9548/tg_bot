import os
import re
from TechVJ.cleaner import clean_filename

ILLEGAL_FS_CHARS = r'[\/:*?\"<>|]'

def clean_title_str(t: str) -> str:
    """Removes filesystem-illegal characters and normalizes whitespace."""
    if not t:
        return ""
    t = re.sub(ILLEGAL_FS_CHARS, " - ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip(" .-_")


def parse_tg_link(url: str):
    """
    Parses any Telegram message link, forum topic link, or post range.
    Supports:
      - Forum topic range: https://t.me/c/3641059847/1321/1300-1450
      - Forum topic single: https://t.me/c/3641059847/1321/1413
      - Forum topic root:   https://t.me/c/3641059847/1321
      - Private chat range: https://t.me/c/1234567890/100-120
      - Private chat single:https://t.me/c/1234567890/456
      - Public chat range:  https://t.me/channel_name/100-120
      - Public chat single: https://t.me/channel_name/456
    """
    if not url:
        return None
    url = url.strip().split("?")[0].rstrip("/")

    # 1. Private chat or Forum Topic (starts with t.me/c/)
    m_c = re.match(r"https?://t\.me/c/(\d+)/(.+)$", url)
    if m_c:
        chat_id = int("-100" + m_c.group(1))
        rest = [x for x in m_c.group(2).split("/") if x]

        # Case A: Standard private chat: c/<chat_id>/<msg_spec>
        if len(rest) == 1:
            parts = rest[0].split("-")
            try:
                from_id = int(parts[0].strip())
                to_id = int(parts[1].strip()) if len(parts) > 1 else from_id
                return {
                    "kind": "channel",
                    "chat_id": chat_id,
                    "topic_id": from_id,
                    "from_id": from_id,
                    "to_id": to_id,
                    "raw_link": url
                }
            except ValueError:
                return None

        # Case B: Forum topic link: c/<chat_id>/<topic_id>/<msg_spec>
        elif len(rest) >= 2:
            try:
                topic_id = int(rest[0].strip())
                parts = rest[1].split("-")
                from_id = int(parts[0].strip())
                to_id = int(parts[1].strip()) if len(parts) > 1 else from_id
                return {
                    "kind": "topic",
                    "chat_id": chat_id,
                    "topic_id": topic_id,
                    "from_id": from_id,
                    "to_id": to_id,
                    "raw_link": url
                }
            except ValueError:
                return None

    # 2. Public Channel link: t.me/<username>/<msg_spec>
    m_pub = re.match(r"https?://t\.me/([a-zA-Z0-9_]+)/(\d+)(?:-(\d+))?$", url)
    if m_pub:
        username = m_pub.group(1)
        from_id = int(m_pub.group(2))
        to_id = int(m_pub.group(3)) if m_pub.group(3) else from_id
        return {
            "kind": "public",
            "chat_id": None,
            "username": username,
            "topic_id": None,
            "from_id": from_id,
            "to_id": to_id,
            "raw_link": url
        }

    return None


def parse_course_metadata(caption: str, orig_filename: str = ""):
    """
    Dynamically extracts:
      - serial (e.g. '300', '301', '45', '01')
      - title (Subject, Lecture title, or Chapter name across any course/topic)
      - part (e.g. 'Part 1', 'Part 2', etc.)
    """
    serial = None
    title = None
    part = None

    text = caption or ""

    # 1. Extract Serial / Number (e.g. ——— ✦ 300 ✦ ———, ✦ 300 ✦, #300, or 300.)
    m_serial = re.search(r"(?:✦|#|—)\s*(\d+)\s*(?:✦|—)?", text)
    if m_serial:
        serial = m_serial.group(1).strip()
    else:
        m_s2 = re.search(r"^\s*(\d+)\s*[\.\-\)]", text, re.MULTILINE)
        if m_s2:
            serial = m_s2.group(1).strip()

    # 2. Extract Part (e.g. ⋅ ⋅ ─ ─ Part 1 ─ ─ ⋅ ⋅, Part 1, Part 02, Pt. 1)
    m_part = re.search(r"(?:⋅\s*⋅\s*─\s*─\s*)?(?:Part|Pt\.?|Episode|Ep\.?)\s*(\d+)", text, re.IGNORECASE)
    if m_part:
        part = f"Part {int(m_part.group(1))}"
    else:
        # Check in orig_filename if not found in caption
        m_part_fn = re.search(r"(?:Part|Pt\.?)\s*(\d+)", orig_filename, re.IGNORECASE)
        if m_part_fn:
            part = f"Part {int(m_part_fn.group(1))}"

    # 3. Extract Subject / Lecture Title generically for any topic
    # Check bullet point lines first: • <Title>
    bullet_candidates = re.findall(r"^[•\-\*]\s*([A-Za-z0-9].*?)(?:\r?\n|$)", text, re.MULTILINE)
    for c in bullet_candidates:
        c_clean = clean_title_str(c)
        # Skip generic batch descriptor lines or part lines
        if re.search(r"(?i)\b(?:live\s*batch|foundation\s*course|batch\s*20\d\d|part\s*\d+)\b", c_clean):
            continue
        if len(c_clean) >= 3:
            title = c_clean
            break

    # Fallback: find any line with lecture/chapter or subject name
    if not title:
        for line in text.splitlines():
            line_clean = clean_title_str(line.strip(" •-*—✦⋅"))
            if not line_clean or len(line_clean) < 3:
                continue
            if re.search(r"(?i)\b(?:part\s*\d+|^\d+$|live\s*online|foundation\s*course)\b", line_clean):
                continue
            title = line_clean
            break

    # If caption had no title, fall back to clean orig_filename without extension
    if not title and orig_filename:
        stem = orig_filename.rsplit(".", 1)[0]
        title = clean_title_str(clean_filename(stem))

    return serial, title, part


def format_organized_filename(caption: str, orig_filename: str, prefix: str = "", custom_removals: list = None) -> str:
    """
    Constructs an organized filename:
      [300] EM - Lecture 6 (Vector Calculus) - Part 1.mp4
      [300] EM - Lecture 6 (Vector Calculus) - Part 2.mp4
      [301] EM - Lecture 7.mp4
    Works universally across ANY subject, topic, and file extension.
    """
    ext = orig_filename.rsplit(".", 1)[-1] if "." in orig_filename else "mp4"
    serial, title, part = parse_course_metadata(caption, orig_filename)

    if serial and title:
        # Standardize serial tag with 3 digits padding if numeric
        s_val = serial.zfill(3) if serial.isdigit() and len(serial) < 3 else serial
        s_tag = f"[{s_val}]"

        clean_title = clean_filename(f"{title}.{ext}", custom_removals=custom_removals).rsplit(".", 1)[0]

        if part:
            stem = f"{s_tag} {clean_title} - {part}"
        else:
            stem = f"{s_tag} {clean_title}"

        if prefix and prefix.strip():
            stem = f"{prefix.strip()} {stem}"

        return f"{stem}.{ext}"

    # Fallback to standard filename cleaner
    return clean_filename(orig_filename, prefix=prefix, custom_removals=custom_removals)


def format_organized_caption(caption: str, organized_name: str, filesize: str, custom_tmpl: str = None) -> str:
    """
    Formats a clean, standardized Telegram caption for transferred files.
    """
    if custom_tmpl:
        return custom_tmpl.replace("{filename}", organized_name).replace("{size}", filesize).replace("{caption}", caption or "")

    serial, title, part = parse_course_metadata(caption, organized_name)
    if title:
        serial_str = f"🔢 **Lecture/Serial:** `#{serial}`\n" if serial else ""
        part_str = f"🧩 **Part:** `{part}`\n" if part else ""
        return (
            f"📚 **{title}**\n"
            f"{serial_str}"
            f"{part_str}"
            f"📁 **File:** `{organized_name}`\n"
            f"📦 **Size:** `{filesize}`"
        )

    # Standard fallback
    return f"📁 **{organized_name}**\n📦 **Size:** `{filesize}`"


class AuditTracker:
    """Tracks transferred items and generates a complete verification checklist."""
    def __init__(self, topic_title: str = "Batch"):
        self.topic_title = topic_title
        self.items = []

    def record_item(self, post_id: int, serial: str, title: str, part: str, filename: str, status: str = "success"):
        self.items.append({
            "post_id": post_id,
            "serial": serial or str(post_id),
            "title": title or filename,
            "part": part or "",
            "filename": filename,
            "status": status
        })

    def generate_report(self) -> str:
        total = len(self.items)
        if total == 0:
            return "📊 **Transfer Summary:** No files were processed."

        success_items = [i for i in self.items if i["status"] == "success"]
        failed_items = [i for i in self.items if i["status"] != "success"]

        lines = [
            f"📊 **Transfer Audit & Organization Report**",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📚 **Target:** `{self.topic_title}`",
            f"📁 **Total Processed:** `{total}`",
            f"✅ **Transferred:** `{len(success_items)}`",
            f"❌ **Skipped / Failed:** `{len(failed_items)}`",
            "",
            "📋 **Chronological Checklist:**"
        ]

        # Display checklist (limit to first 30 if very long to stay within TG message limit)
        display_items = success_items[:30]
        for it in display_items:
            s_tag = f"✦ {it['serial']} ✦" if it['serial'] else f"#{it['post_id']}"
            p_tag = f" — {it['part']}" if it['part'] else ""
            lines.append(f"  ✅ {s_tag} {it['title'][:40]}{p_tag}")

        if len(success_items) > 30:
            lines.append(f"  *(...and {len(success_items) - 30} more items in sequence)*")

        lines.append("")
        if len(failed_items) == 0:
            lines.append("🎉 **Status:** 100% Complete & Verified! All parts preserved.")
        else:
            lines.append(f"⚠️ **Note:** `{len(failed_items)}` items were skipped or failed.")

        return "\n".join(lines)
