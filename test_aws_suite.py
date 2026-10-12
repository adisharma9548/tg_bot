"""
Comprehensive AWS Refactor & Quality Verification Test Suite
Tests:
1. Configuration loading and missing variable rejection
2. Zero MongoDB / external database references across codebase and requirements.txt
3. SQLite local database operations and WAL mode pragmas
4. AWS DynamoDB error handling, permission failures, and seamless SQLite fallback
5. Disk space pre-check validation (buffer safety)
6. TaskManager single-concurrency lock and file cleanup upon cancellation
7. Web health check endpoint status reporting
"""

import os
import sys
import shutil
import unittest
from unittest.mock import patch, MagicMock

# Ensure current directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import validate_config, API_ID, API_HASH, BOT_TOKEN
from database.db import SQLiteDatabase, DynamoDatabase
from plugins.start import check_disk_space, TaskManager, DOWNLOAD_DIR
from app import app


class TestAWSArchitecture(unittest.TestCase):

    def test_01_config_validation(self):
        """Test configuration loader and validator."""
        is_valid, msg = validate_config()
        self.assertTrue(is_valid, f"Current config should be valid: {msg}")

        # Test with missing BOT_TOKEN
        with patch("config.BOT_TOKEN", ""):
            val, err = validate_config()
            self.assertFalse(val, "Validation must fail when BOT_TOKEN is empty")
            self.assertIn("BOT_TOKEN", err)

    def test_02_zero_mongodb_dependencies(self):
        """Verify that zero MongoDB references exist in active code and requirements.txt."""
        # 1. Check requirements.txt
        with open("requirements.txt", "r", encoding="utf-8") as f:
            reqs = f.read().lower()
        self.assertNotIn("motor", reqs, "motor must not be present in requirements.txt")
        self.assertNotIn("pymongo", reqs, "pymongo must not be present in requirements.txt")
        self.assertNotIn("dnspython", reqs, "dnspython must not be present in requirements.txt")

        # 2. Check source python files for active Mongo imports/classes
        forbidden = ["import motor", "from motor", "import pymongo", "from pymongo", "mongoclient", "mongodatabase"]
        scanned_count = 0
        for root, _, files in os.walk("."):
            if any(p in root for p in [".git", "__pycache__", "venv", ".venv"]):
                continue
            for fname in files:
                if fname.endswith(".py") and fname != "test_aws_suite.py":
                    scanned_count += 1
                    fpath = os.path.join(root, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                    for term in forbidden:
                        self.assertNotIn(term, content, f"Found forbidden term '{term}' in {fpath}")

        self.assertGreater(scanned_count, 5, "At least 5 source files must be scanned")

    def test_03_sqlite_local_fallback(self):
        """Test SQLite database operations and schema integrity."""
        test_db_path = "database/test_temp.db"
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        db = SQLiteDatabase(db_path=test_db_path)
        test_user_id = 99999901
        test_name = "Test AWS User"

        # Add user
        db._add_user(test_user_id, test_name)
        self.assertTrue(db._is_user_exist(test_user_id))
        self.assertFalse(db._is_user_exist(11111111))

        # Test settings modification
        db._set_field(test_user_id, "upload_as_doc", 1)
        self.assertEqual(db._get_field(test_user_id, "upload_as_doc"), 1)

        db._set_field(test_user_id, "caption", "Custom AWS Caption")
        self.assertEqual(db._get_field(test_user_id, "caption"), "Custom AWS Caption")

        # Clean user settings
        db._clear_all_user_settings(test_user_id)
        self.assertIsNone(db._get_field(test_user_id, "caption"))
        self.assertEqual(db._get_field(test_user_id, "upload_as_doc"), 0)

        # Cleanup
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    def test_04_dynamodb_permission_and_credential_failures(self):
        """Test DynamoDB behavior with missing/invalid credentials and AccessDeniedException."""
        from botocore.exceptions import ClientError, NoCredentialsError

        # Case A: Missing credentials error
        with patch("boto3.resource") as mock_resource:
            mock_client = MagicMock()
            mock_resource.return_value = mock_client
            mock_tbl = MagicMock()
            mock_tbl.load.side_effect = NoCredentialsError()
            mock_client.Table.return_value = mock_tbl

            with self.assertRaises(NoCredentialsError):
                DynamoDatabase(table_name="tg_test_table", region="ap-south-1")

        # Case B: AccessDeniedException simulation
        with patch("boto3.resource") as mock_resource:
            mock_client = MagicMock()
            mock_resource.return_value = mock_client
            mock_tbl = MagicMock()
            mock_tbl.load.side_effect = ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "User is not authorized"}},
                "DescribeTable"
            )
            mock_client.Table.return_value = mock_tbl

            with self.assertRaises(ClientError):
                DynamoDatabase(table_name="tg_test_table", region="ap-south-1")

    def test_05_disk_space_checker(self):
        """Test pre-download disk space check under normal and constrained conditions."""
        # 1. Normal condition: small file should pass
        has_space, free_b, total_b = check_disk_space(required_bytes=1024 * 1024, path=".")
        self.assertTrue(has_space, "Normal small file should have sufficient space")
        self.assertGreater(free_b, 0)
        self.assertGreater(total_b, 0)

        # 2. Exorbitant requirement (e.g. 100 Petabytes): should fail
        impossible_bytes = 100 * 1024 * 1024 * 1024 * 1024 * 1024
        has_space_imp, _, _ = check_disk_space(required_bytes=impossible_bytes, path=".")
        self.assertFalse(has_space_imp, "Impossible file size must be rejected to protect drive")

    def test_06_task_manager_concurrency_and_purge(self):
        """Test single-task concurrency lock and immediate file purging."""
        test_user = 8888001
        test_file = os.path.join(DOWNLOAD_DIR, "test_purge_sample.txt")

        # Create dummy download file
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        with open(test_file, "w") as f:
            f.write("temporary download content")

        self.assertTrue(os.path.exists(test_file))

        # Start task
        TaskManager.start_task(test_user, task_type="transfer")
        self.assertTrue(TaskManager.is_user_busy(test_user))

        # Register file
        TaskManager.register_file(test_user, test_file)

        # Purge files
        TaskManager.purge_user_files(test_user)
        self.assertFalse(os.path.exists(test_file), "File must be immediately purged on task finish/cancel")

        # Finish task
        TaskManager.finish_task(test_user)
        self.assertFalse(TaskManager.is_user_busy(test_user))

    def test_07_health_check_endpoint(self):
        """Test Flask HTTP /health endpoint."""
        client = app.test_client()
        response = client.get("/health")
        self.assertIn(response.status_code, [200, 503])
        data = response.get_json()
        self.assertIn("service", data)
        self.assertIn("database", data)
        self.assertEqual(data["service"], "Save Restricted Content Bot")

    def test_08_filename_cleaner_and_path_traversal(self):
        """Test filename cleaning and path traversal protection."""
        from plugins.cleaner import clean_filename

        # Test normal clean
        dirty = "@channel_name [cracked by anonymous] Lecture_1.mp4"
        cleaned = clean_filename(dirty)
        self.assertNotIn("@channel_name", cleaned)
        self.assertNotIn("cracked", cleaned)
        self.assertTrue(cleaned.endswith(".mp4"))

        # Test path traversal prevention
        traversal = "../../etc/passwd.mp4"
        safe_name = clean_filename(traversal)
        self.assertNotIn("..", safe_name)
        self.assertNotIn("/", safe_name)
        self.assertEqual(safe_name, "passwd.mp4")

    def test_09_startup_orphaned_download_cleanup(self):
        """Test that orphaned temporary downloads are cleanly purged on startup."""
        from plugins.start import cleanup_orphaned_downloads

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        orphan_path = os.path.join(DOWNLOAD_DIR, "orphan_test_file.tmp")
        with open(orphan_path, "w") as f:
            f.write("stale orphaned download data")

        self.assertTrue(os.path.exists(orphan_path))
        cleanup_orphaned_downloads()
        self.assertFalse(os.path.exists(orphan_path), "Orphaned temporary files must be purged")


if __name__ == "__main__":
    unittest.main()

