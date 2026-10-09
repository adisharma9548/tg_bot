import os
import re
import time

def clean_filename(filename: str, prefix: str = "", custom_removals: list = None) -> str:
    """Cleans annoying channel usernames, ads, and phrases from filename while preserving extension."""
    if not filename or "." not in filename:
        return filename or "file"

    stem, ext = filename.rsplit(".", 1)
    clean_stem = stem

    # 1. Remove custom user-defined words if set
    if custom_removals:
        for word in custom_removals:
            if word and word.strip():
                clean_stem = re.sub(re.escape(word.strip()), "", clean_stem, flags=re.IGNORECASE)

    # 2. Remove promo phrases like 'cracked by...', 'extracted by...', etc.
    clean_stem = re.sub(
        r"(?i)(?:^|[\s_\-\[\(])(?:cracked|extracted|downloaded|uploaded|shared|provided|ripped|encoded|compressed)\s*(?:by|from)?\s*[:\-_]?\s*[^\s_\-\]\)]+",
        "",
        clean_stem
    )

    # 3. Remove Telegram channel/usernames like @channel_name
    clean_stem = re.sub(r"@[a-zA-Z0-9_]+?(?=[_\s\.\-]|[\(\)\[\]]|$)", "", clean_stem)

    # 4. Remove URLs and domain links
    clean_stem = re.sub(r"https?://\S+|www\.\S+|t\.me/\S+", "", clean_stem)

    # 5. Clean empty or orphaned brackets
    clean_stem = re.sub(r"\[\s*\]|\(\s*\)|\{\s*\}", "", clean_stem)
    clean_stem = re.sub(r"^[\s\]\)\}-]+|[\s\[\(\{_-]+$", "", clean_stem)

    # 6. Normalize repeated separators
    clean_stem = re.sub(r"[_]{2,}", "_", clean_stem)
    clean_stem = re.sub(r"[-]{2,}", "-", clean_stem)
    clean_stem = re.sub(r"[\.]{2,}", ".", clean_stem)
    clean_stem = re.sub(r"\s+", " ", clean_stem)

    # 7. Strip leftover boundary punctuation
    clean_stem = clean_stem.strip(" .-_")

    # Fallback if stem was entirely wiped
    if not clean_stem:
        clean_stem = stem.strip(" .-_") or "file"

    # 8. Apply custom prefix if configured
    if prefix and prefix.strip():
        final_stem = f"{prefix.strip()} {clean_stem}".strip()
    else:
        final_stem = clean_stem

    return f"{final_stem}.{ext}"

def rename_file_clean(filepath: str, prefix: str = "", custom_removals: list = None) -> str:
    """Renames file on disk with cleaned name and returns new filepath."""
    if not filepath or not os.path.exists(filepath):
        return filepath

    dir_name = os.path.dirname(filepath)
    orig_name = os.path.basename(filepath)
    cleaned_name = clean_filename(orig_name, prefix=prefix, custom_removals=custom_removals)

    if cleaned_name == orig_name:
        return filepath

    new_path = os.path.join(dir_name, cleaned_name)
    try:
        if os.path.exists(new_path) and new_path != filepath:
            name, ext = os.path.splitext(cleaned_name)
            new_path = os.path.join(dir_name, f"{name}_{int(time.time())}{ext}")
        os.rename(filepath, new_path)
        return new_path
    except Exception:
        return filepath
