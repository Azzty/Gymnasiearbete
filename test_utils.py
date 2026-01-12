import unittest
import os
import pandas as pd
import shutil
import tempfile
import sys
import importlib


class TestUtils(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load the real utils module before any test mocking occurs."""
        # Force import the utils module directly before test discovery mocks it
        spec = importlib.util.spec_from_file_location(
            "utils_real",
            os.path.join(os.path.dirname(__file__), "utils.py")
        )
        cls.utils_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.utils_module)
    
    def setUp(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.original_path = self.utils_module.PATH_TILL_PRISER
        
    def tearDown(self):
        # Remove the directory after the test and restore original path
        shutil.rmtree(self.test_dir)
        self.utils_module.PATH_TILL_PRISER = self.original_path

    def test_functions_exist(self):
        """Test that required functions exist in utils module."""
        self.assertTrue(hasattr(self.utils_module, '_read_and_process_ticker'))
        self.assertTrue(hasattr(self.utils_module, 'retrieve_data'))
        self.assertTrue(callable(self.utils_module._read_and_process_ticker))
        self.assertTrue(callable(self.utils_module.retrieve_data))
    
    def test_error_codes_enum(self):
        """Test that ERROR_CODES enum has expected values."""
        self.assertTrue(hasattr(self.utils_module, 'ERROR_CODES'))
        self.assertEqual(self.utils_module.ERROR_CODES.SUCCESS.value, 0)
        self.assertEqual(self.utils_module.ERROR_CODES.INVALID_TICKER.value, 1)
        self.assertEqual(self.utils_module.ERROR_CODES.INVALID_AMOUNT.value, 2)

    def test_read_and_process_ticker_no_file(self):
        """Test that it handles missing files gracefully."""
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker("NON_EXISTENT", 10)
        ticker, df = result
        self.assertEqual(ticker, "NON_EXISTENT")
        self.assertIsNone(df)

    def test_read_and_process_ticker_basic(self):
        """Test reading a standard CSV and resampling logic."""
        ticker = "TEST_TICKER"
        csv_path = os.path.join(self.test_dir, f"{ticker}.csv")
        
        data = [
            "TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME",
            "10:00:00,100,0,0,1000",
            "10:00:30,101,0,0,1500",
            "10:01:00,102,0,0,2000",
            "10:02:00,101,0,0,2500"
        ]
        
        with open(csv_path, 'w', newline='') as f:
            f.write("\n".join(data))
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker(ticker, 60)
        t, df = result
        
        self.assertEqual(t, ticker)
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 3)
        
        row_0 = df.iloc[0]
        self.assertEqual(row_0['OPEN'], 100.0)
        self.assertEqual(row_0['HIGH'], 101.0)
        self.assertEqual(row_0['PRICE'], 101.0)
        self.assertEqual(row_0['VOLUME'], 0.0) 
        
        row_1 = df.iloc[1]
        self.assertEqual(row_1['PRICE'], 102.0)
        self.assertEqual(row_1['VOLUME'], 500.0)

    def test_read_and_process_ticker_low_value(self):
        """Test that LOW value is calculated correctly."""
        ticker = "LOW_TEST"
        csv_path = os.path.join(self.test_dir, f"{ticker}.csv")
        
        data = [
            "TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME",
            "10:00:00,100,0,0,1000",
            "10:00:15,95,0,0,1100",
            "10:00:30,98,0,0,1200",
            "10:01:00,105,0,0,1300"
        ]
        
        with open(csv_path, 'w', newline='') as f:
            f.write("\n".join(data))
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker(ticker, 60)
        t, df = result
        
        self.assertEqual(t, ticker)
        self.assertFalse(df.empty)
        
        # Check that LOW is correctly calculated as the minimum price in each minute
        row_0 = df.iloc[0]
        self.assertEqual(row_0['LOW'], 95.0)  # Min of [100, 95, 98]
        self.assertEqual(row_0['OPEN'], 100.0)  # First price
        self.assertEqual(row_0['HIGH'], 100.0)  # Max of [100, 95, 98]
        self.assertEqual(row_0['PRICE'], 98.0)  # Last price

    def test_retrieve_data_empty_ticker_list(self):
        """Test retrieve_data with empty ticker list."""
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        data = self.utils_module.retrieve_data([], 10)
        self.assertEqual(len(data), 0)
        self.assertIsInstance(data, dict)

    def test_retrieve_data_mixed_valid_invalid(self):
        """Test retrieve_data with mix of valid and invalid tickers."""
        # Create file for T1
        with open(os.path.join(self.test_dir, "T1.csv"), 'w') as f:
            f.write("TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME\n")
            f.write("12:00:00,50,0,0,100\n")
            f.write("12:01:00,51,0,0,150\n")
        
        # T2 file doesn't exist
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        data = self.utils_module.retrieve_data(["T1", "T2", "T3"], 10)
        
        # Only T1 should be in results
        self.assertEqual(len(data), 1)
        self.assertIn("T1", data)
        self.assertNotIn("T2", data)
        self.assertNotIn("T3", data)
        self.assertIsInstance(data["T1"], pd.DataFrame)

    def test_read_and_process_ticker_single_row(self):
        """Test reading CSV with only one data row."""
        ticker = "SINGLE"
        csv_path = os.path.join(self.test_dir, f"{ticker}.csv")
        
        data = [
            "TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME",
            "10:00:00,100,0,0,1000"
        ]
        
        with open(csv_path, 'w', newline='') as f:
            f.write("\n".join(data))
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker(ticker, 60)
        t, df = result
        
        self.assertEqual(t, ticker)
        self.assertFalse(df.empty)
        self.assertEqual(len(df), 1)
        
        row = df.iloc[0]
        self.assertEqual(row['OPEN'], 100.0)
        self.assertEqual(row['HIGH'], 100.0)
        self.assertEqual(row['LOW'], 100.0)
        self.assertEqual(row['PRICE'], 100.0)

    def test_read_and_process_ticker_invalid_time_format(self):
        """Test CSV with invalid time formats."""
        ticker = "INVALID_TIME"
        csv_path = os.path.join(self.test_dir, f"{ticker}.csv")
        
        data = [
            "TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME",
            "10:00:00,100,0,0,1000",
            "invalid_time,101,0,0,1100",  # Invalid format
            "10:01:00,102,0,0,1200"
        ]
        
        with open(csv_path, 'w', newline='') as f:
            f.write("\n".join(data))
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker(ticker, 60)
        t, df = result
        
        self.assertEqual(t, ticker)
        # Invalid times should be dropped, leaving only valid rows
        self.assertEqual(len(df), 2)

    def test_read_and_process_ticker_non_numeric_price(self):
        """Test CSV with non-numeric price data."""
        ticker = "NON_NUMERIC"
        csv_path = os.path.join(self.test_dir, f"{ticker}.csv")
        
        data = [
            "TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME",
            "10:00:00,100,0,0,1000",
            "10:00:30,not_a_number,0,0,1100",  # Non-numeric price
            "10:01:00,102,0,0,1200"
        ]
        
        with open(csv_path, 'w', newline='') as f:
            f.write("\n".join(data))
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker(ticker, 60)
        t, df = result
        
        self.assertEqual(t, ticker)
        # Non-numeric prices should be converted to NaN and handled gracefully
        self.assertFalse(df.empty)
        # Should still have valid rows
        self.assertGreater(len(df), 0)

    def test_read_and_process_ticker_with_header(self):
        """Test that header row is properly handled."""
        ticker = "WITH_HEADER"
        csv_path = os.path.join(self.test_dir, f"{ticker}.csv")
        
        data = [
            "TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME",
            "10:00:00,100,0,0,1000",
            "10:01:00,101,0,0,1100"
        ]
        
        with open(csv_path, 'w', newline='') as f:
            f.write("\n".join(data))
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker(ticker, 60)
        t, df = result
        
        self.assertEqual(t, ticker)
        # Should have 2 data rows, not 3 (header should be removed)
        self.assertEqual(len(df), 2)
        # Verify actual data, not header
        self.assertEqual(df.iloc[0]['PRICE'], 100.0)
        self.assertEqual(df.iloc[1]['PRICE'], 101.0)
        """Test that empty files don't crash the reader."""
        ticker = "EMPTY"
        csv_path = os.path.join(self.test_dir, f"{ticker}.csv")
        open(csv_path, 'w').close()
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        result = self.utils_module._read_and_process_ticker(ticker, 10)
        t, df = result
        self.assertEqual(t, ticker)
        # Empty file returns an empty DataFrame, not None
        self.assertTrue(df.empty)

    def test_retrieve_data(self):
        """Test the threaded data retrieval."""
        t1, t2 = "T1", "T2"
        for t in [t1, t2]:
            with open(os.path.join(self.test_dir, f"{t}.csv"), 'w') as f:
                f.write("TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME\n")
                f.write("12:00:00,50,0,0,100\n")
                f.write("12:01:00,51,0,0,150\n")
                f.write("12:02:00,52,0,0,200\n")
                f.write("12:03:00,53,0,0,250\n")
                f.write("12:04:00,54,0,0,300\n")
                f.write("12:05:00,55,0,0,350\n")
                f.write("12:06:00,56,0,0,400\n")
                f.write("12:07:00,57,0,0,450\n")
                f.write("12:08:00,58,0,0,500\n")
                f.write("12:09:00,59,0,0,550\n")
        
        self.utils_module.PATH_TILL_PRISER = self.test_dir
        data = self.utils_module.retrieve_data([t1, t2], 10)
        self.assertEqual(len(data), 2)
        self.assertIn(t1, data)
        self.assertIn(t2, data)
        self.assertIsInstance(data[t1], pd.DataFrame)

if __name__ == '__main__':
    unittest.main()