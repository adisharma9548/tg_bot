"""
AWS Elastic Beanstalk POSIX-compliant Zip Packager
Ensures all file paths inside the zip use forward slashes ('/') so Linux /usr/bin/unzip unpacks cleanly.
"""

import os
import zipfile

OUTPUT_ZIP = "tg_bot_aws.zip"

INCLUDE_DIRS = [
    "plugins",
    "database",
    ".ebextensions",
    ".github"
]

INCLUDE_FILES = [
    "Dockerfile",
    "Procfile",
    "app.py",
    "application.py",
    "bot.py",
    "config.py",
    "guard.py",
    "runner.py",
    "requirements.txt",
    "docker-compose.yml",
    ".cursorrules",
    "CLAUDE.md",
    "AGENT_PROMPT.md",
    "README.md",
    "AWS_DEPLOYMENT_GUIDE.md",
    "logo.jpg",
    "migrate_sqlite_to_mongodb.py"
]

EXCLUDE_EXTS = [
    ".pyc",
    ".session",
    ".session-journal",
    ".db",
    ".db-shm",
    ".db-wal",
    ".tmp",
    ".log",
    ".zip"
]

EXCLUDE_DIRS = [
    "__pycache__",
    ".git",
    "venv",
    ".venv",
    "downloads"
]


def build_zip():
    print(f"[*] Packaging {OUTPUT_ZIP} with POSIX forward slashes for Linux...")
    count = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Add top-level individual files
        for f in INCLUDE_FILES:
            if os.path.isfile(f):
                # Ensure POSIX forward slash name
                arcname = f.replace("\\", "/")
                zf.write(f, arcname)
                count += 1

        # 2. Add directories
        for d in INCLUDE_DIRS:
            if os.path.isdir(d):
                for root, dirs, files in os.walk(d):
                    # Filter out excluded directories
                    dirs[:] = [sub for sub in dirs if sub not in EXCLUDE_DIRS and not sub.startswith("__")]
                    for file in files:
                        if any(file.endswith(ext) for ext in EXCLUDE_EXTS):
                            continue
                        full_path = os.path.join(root, file)
                        # CRITICAL FOR LINUX UNZIP: Convert backslashes to forward slashes!
                        arcname = full_path.replace("\\", "/")
                        zf.write(full_path, arcname)
                        count += 1

    file_size_kb = os.path.getsize(OUTPUT_ZIP) / 1024
    print(f"[SUCCESS] Packaged {count} files into '{OUTPUT_ZIP}' ({file_size_kb:.1f} KB).")
    print(f"[+] All internal paths use Linux standard forward slashes ('/').")


if __name__ == "__main__":
    build_zip()
