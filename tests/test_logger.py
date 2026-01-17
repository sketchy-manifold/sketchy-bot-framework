# Read tests/knowledge.md in this directory for how to run tests.
import sys
from pathlib import Path
import unittest
import shutil
import csv
from datetime import datetime

# Ensure the src package is importable when tests are run directly
ROOT_PATH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_PATH))

from src.logger import Logger, ErrorEvent, PlaceBetEvent
from config.log_config import LogConfig

class TestLogger(unittest.TestCase):
    def setUp(self):
        # Create a test logs directory
        self.test_log_dir = Path("test_logs")
        self.test_log_dir.mkdir(exist_ok=True)

        # Enable logging for logger tests
        from config.log_config import LogConfig
        self.original_enabled = LogConfig.ENABLED
        LogConfig.ENABLED = True

        # Store original log directory and replace with test directory
        self.original_log_dir = Logger._instance.log_dir if Logger._instance else None
        Logger._instance = None  # Reset singleton
        logger = Logger()
        logger.log_dir = self.test_log_dir

    def tearDown(self):
        # Restore original log directory
        if self.original_log_dir:
            Logger._instance.log_dir = self.original_log_dir

        from config.log_config import LogConfig
        LogConfig.ENABLED = self.original_enabled

        # Clean up test directory
        shutil.rmtree(self.test_log_dir)

    def test_log_error_event(self):
        """Test logging an error event."""
        logger = Logger()
        event = ErrorEvent(
            error_type="API_ERROR",
            message="Connection failed",
            source="ManifoldClient",
        )
        logger.log(event, "errors")

        # Check file exists and contains correct data
        log_file = self.test_log_dir / "errors" / "errorevent.csv"
        self.assertTrue(log_file.exists())
        
        with open(log_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row['error_type'], "API_ERROR")
            self.assertEqual(row['message'], "Connection failed")
            self.assertEqual(row['source'], "ManifoldClient")
            self.assertIn('context', row)
            self.assertEqual(row['context'], "None")

    def test_multiple_events_same_type(self):
        """Test logging multiple events of the same type."""
        logger = Logger()
        events = [
            PlaceBetEvent(
                id=f"bet_{i}",
                contract_id=f"market_{i}",
                user_id=f"user_{i}",
                outcome="NO",
                amount=100.0,
                filled_amount=100.0,
                shares=200.0,
                limit_prob=0.5,
                expires_at=datetime.now(),
            )
            for i in range(3)
        ]
        
        for event in events:
            logger.log(event, "bets")

        # Check file exists and contains all events
        log_file = self.test_log_dir / "bets" / "placebetevent.csv"
        self.assertTrue(log_file.exists())
        
        with open(log_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 3)
            for i, row in enumerate(rows):
                self.assertEqual(row['contract_id'], f"market_{i}")
                self.assertEqual(row['id'], f"bet_{i}")

    def test_log_rotation(self):
        """Test that log files rotate when exceeding max size."""
        logger = Logger()

        # Temporarily set a very small max file size
        original_max = LogConfig.MAX_LOG_FILE_BYTES
        LogConfig.MAX_LOG_FILE_BYTES = 50

        try:
            # Precreate a file that already exceeds the limit
            domain_dir = self.test_log_dir / "errors"
            domain_dir.mkdir(exist_ok=True)
            oversized = domain_dir / "errorevent.csv"
            with open(oversized, "wb") as f:
                f.write(b"x" * 60)

            event = ErrorEvent(
                error_type="API_ERROR",
                message="A" * 10,
                source="ManifoldClient",
            )

            logger.log(event, "errors")

            # Rotation should create a new file with suffix _2
            rotated = domain_dir / "errorevent_2.csv"
            self.assertTrue(rotated.exists())
        finally:
            LogConfig.MAX_LOG_FILE_BYTES = original_max

if __name__ == '__main__':
    unittest.main()
