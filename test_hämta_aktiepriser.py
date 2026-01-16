import unittest
import tempfile
import shutil
import os
import importlib.util
import time
from threading import Thread
from unittest.mock import Mock


class TestHamtaAktiepriser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load the real module from file so test mocking elsewhere doesn't interfere
        spec = importlib.util.spec_from_file_location(
            "hamta_real",
            os.path.join(os.path.dirname(__file__), "hämta_aktiepriser.py"),
        )
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self):
        # Temporary directory for price files
        self.test_dir = tempfile.mkdtemp()
        # Save original path if present
        self.original_path = getattr(self.module, "PATH_TILL_PRISER", None)
        self.module.PATH_TILL_PRISER = self.test_dir

        # Ensure a clean state for globals used by the module
        with self.module.QUEUE_LOCK:
            self.module.DATA_QUEUE.clear()
        self.module.STOP_EVENT.clear()
        self.module.last_ticker_update = 0.0
        self.module._ws = None
        self.module._writer_thread = None
        self.module._listener_thread = None

    def tearDown(self):
        # Restore state
        shutil.rmtree(self.test_dir)
        if self.original_path is not None:
            self.module.PATH_TILL_PRISER = self.original_path
        self.module.STOP_EVENT.clear()
        with self.module.QUEUE_LOCK:
            self.module.DATA_QUEUE.clear()

    def test_message_handler_appends_to_queue_and_updates_timestamp(self):
        start = time.time()
        msg = {"id": "T1", "time": str(int(time.time() * 1000)), "price": 10, "market_hours": 1}
        self.module.message_handler(msg)

        # Message should be in queue
        with self.module.QUEUE_LOCK:
            self.assertEqual(len(self.module.DATA_QUEUE), 1)
            queued = self.module.DATA_QUEUE[0]
        self.assertEqual(queued["id"], "T1")

        # last_ticker_update should be updated to a recent timestamp
        self.assertGreaterEqual(self.module.last_ticker_update, start)
        self.assertLessEqual(self.module.last_ticker_update, time.time())

    def test_data_writer_creates_csv_and_writes_rows(self):
        # Prepare a message and place it on the queue
        now_ms = int(time.time() * 1000)
        msg = {
            "id": "TESTTICK",
            "time": str(now_ms),
            "price": 123.45,
            "change_percent": 0.1,
            "change": 0.12,
            "day_volume": 1000,
            "market_hours": 1,
        }
        with self.module.QUEUE_LOCK:
            self.module.DATA_QUEUE.append(msg)

        # Prevent watchdog from triggering while we run the writer
        self.module.last_ticker_update = time.time()

        writer_thread = Thread(target=self.module.data_writer, daemon=True)
        writer_thread.start()

        # Give the writer some time to run and process the queue
        time.sleep(0.5)

        # Signal the writer to stop and wait for it
        self.module.STOP_EVENT.set()
        writer_thread.join(timeout=2)

        # Verify file exists and contains header + one data row
        csv_path = os.path.join(self.test_dir, "TESTTICK.csv")
        self.assertTrue(os.path.exists(csv_path), "CSV file was not created by data_writer")

        with open(csv_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]

        # Expect at least header + 1 row
        self.assertGreaterEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("TIME,PRICE,CHANGE_PERCENT"))
        # Data row should contain the price we wrote
        self.assertIn("123.45", lines[1])

    def test_websocket_watchdog_calls_stop_and_monitor(self):
        # Arrange
        self.module._tickers_to_monitor = ["A", "B"]
        self.module.STOP_EVENT.clear()

        mock_stop = Mock()
        mock_monitor = Mock(side_effect=lambda tickers: self.module.STOP_EVENT.set())

        # Replace the real functions with our mocks
        original_stop = self.module.stop_monitoring
        original_monitor = self.module.monitor_stocks
        self.module.stop_monitoring = mock_stop
        self.module.monitor_stocks = mock_monitor

        try:
            # Run watchdog in a background thread with a small timeout
            wd_thread = Thread(target=self.module.websocket_watchdog, args=(1,), daemon=True)
            wd_thread.start()

            # Wait for the monitor to be called (which will set STOP_EVENT)
            start = time.time()
            while not mock_monitor.called and time.time() - start < 5:
                time.sleep(0.1)

            self.assertTrue(mock_stop.called, "stop_monitoring should have been called by watchdog")
            self.assertTrue(mock_monitor.called, "monitor_stocks should have been called by watchdog")

            # Ensure watchdog thread exits after monitor sets STOP_EVENT
            wd_thread.join(timeout=2)
            self.assertFalse(wd_thread.is_alive(), "watchdog thread did not stop after STOP_EVENT was set")
        finally:
            # Restore originals
            self.module.stop_monitoring = original_stop
            self.module.monitor_stocks = original_monitor


if __name__ == "__main__":
    unittest.main()
