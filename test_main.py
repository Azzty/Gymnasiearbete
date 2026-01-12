import sys
import unittest
from unittest.mock import MagicMock, patch
import datetime
from zoneinfo import ZoneInfo
import inspect

# --- Mock dependencies before importing main ---
# This is necessary because main.py imports these modules at top level,
# and they might not be available or have side effects (like connecting to internet).

mock_hitta_100 = MagicMock()
# main.py calls .split(" ") on the result, so it must be a string
mock_hitta_100.get_most_active_stocks.return_value = "AAPL MSFT NVDA"
sys.modules['hitta_100'] = mock_hitta_100

sys.modules['hämta_aktiepriser'] = MagicMock()
sys.modules['mäklare'] = MagicMock()
sys.modules['handla_aktie'] = MagicMock()
# We can let utils be imported normally or mock it. 
# Since we want to test main's logic, mocking utils avoids file I/O.
sys.modules['utils'] = MagicMock()

# Now import main
import main

class TestMain(unittest.TestCase):
    
    def test_us_market_open_open(self):
        """Test a time when the market should be open (Monday 10:00 NY)."""
        ny_tz = ZoneInfo("America/New_York")
        # Jan 23, 2023 was a Monday
        mock_now = datetime.datetime(2023, 1, 23, 10, 0, 0, tzinfo=ny_tz)
        self.assertTrue(main.us_market_open(mock_now))

    def test_us_market_open_closed_morning(self):
        """Test a time before market open (Monday 09:00 NY)."""
        ny_tz = ZoneInfo("America/New_York")
        mock_now = datetime.datetime(2023, 1, 23, 9, 0, 0, tzinfo=ny_tz)
        self.assertFalse(main.us_market_open(mock_now))

    def test_us_market_open_closed_evening(self):
        """Test a time after market close (Monday 16:01 NY)."""
        ny_tz = ZoneInfo("America/New_York")
        mock_now = datetime.datetime(2023, 1, 23, 16, 1, 0, tzinfo=ny_tz)
        self.assertFalse(main.us_market_open(mock_now))

    def test_us_market_open_weekend(self):
        """Test a weekend (Saturday)."""
        ny_tz = ZoneInfo("America/New_York")
        # Jan 21, 2023 was a Saturday
        mock_now = datetime.datetime(2023, 1, 21, 12, 0, 0, tzinfo=ny_tz)
        self.assertFalse(main.us_market_open(mock_now))

    def test_get_time_to_market_close(self):
        """Test calculation of time remaining until close."""
        ny_tz = ZoneInfo("America/New_York")
        # 15:00 NY. Market closes at 16:00. Delta should be 1 hour.
        now = datetime.datetime(2023, 1, 23, 15, 0, 0, tzinfo=ny_tz)
        delta = main.get_time_to_market_close(now)
        self.assertEqual(delta.total_seconds(), 3600)

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_is_ticker_owned(self, mock_json, mock_open, mock_exists):
        """Test checking if a ticker is owned by any bot."""
        mock_exists.return_value = True
        # Mock portfolio: AAPL is owned (10), MSFT is 0 (not really owned)
        mock_json.return_value = {"aktier": {"AAPL": 10, "MSFT": 0}}
        
        # Inject a mock bot into main.bots
        # main.bots is usually populated in __main__, so it's empty on import
        Bot = MagicMock()
        Bot.bot_name = "test_bot"
        main.bots = [Bot]
        
        self.assertTrue(main.is_ticker_owned("AAPL"))
        self.assertFalse(main.is_ticker_owned("MSFT")) # Amount is 0
        self.assertFalse(main.is_ticker_owned("GOOG")) # Not in dict

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_get_all_owned_tickers(self, mock_json_load, mock_open, mock_exists):
        """Test retrieving all unique tickers owned across multiple bots."""
        mock_exists.return_value = True

        # Mock portfolios for two bots
        mock_json_load.side_effect = [
            {"fria_pengar": 1000, "aktier": {"AAPL": 5, "GOOG": 2}},
            {"fria_pengar": 2000, "aktier": {"MSFT": 3, "AAPL": 0}} # AAPL amount is 0 here
        ]

        # Setup mock bots
        mock_bot1 = MagicMock()
        mock_bot1.bot_name = "bot1"
        mock_bot2 = MagicMock()
        mock_bot2.bot_name = "bot2"
        bots = [mock_bot1, mock_bot2]

        owned = main.get_all_owned_tickers(bots)
        self.assertEqual(owned, {"AAPL", "GOOG", "MSFT"})
        self.assertEqual(mock_open.call_count, 2) # Called once for each bot

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_get_bot_owned_tickers(self, mock_json_load, mock_open, mock_exists):
        """Test retrieving tickers owned by a single bot."""
        mock_exists.return_value = True
        mock_json_load.return_value = {"fria_pengar": 1000, "aktier": {"AAPL": 5, "MSFT": 0, "GOOG": 2}}

        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"

        owned = main.get_bot_owned_tickers(mock_bot)
        self.assertEqual(owned, {"AAPL", "GOOG"})

    @patch('main.get_time_to_market_close')
    @patch('main.ha')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_trade_suggestions_buy(self, mock_json_load, mock_open, mock_exists, mock_ha, mock_time_close):
        """Test executing a BUY suggestion."""
        mock_exists.return_value = True
        # Portfolio has money
        mock_json_load.return_value = {"fria_pengar": 10000, "aktier": {}}
        
        # Mock time to close > 10 mins
        mock_time_close.return_value = datetime.timedelta(minutes=30)
        
        # Setup price data
        main.price_data = {}
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.iloc.__getitem__.return_value = 100.0
        main.price_data["AAPL"] = mock_df
        
        # Mock bot
        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"
        mock_bot.risk = 0.1 # 10% risk
        
        suggestions = {"AAPL": "BUY"}
        
        # Mock ha.utför_flera_transaktioner return value
        mock_ha.utför_flera_transaktioner.return_value = [main.ERROR_CODES.SUCCESS]
        
        main.trade_suggestions(mock_bot, suggestions)
        
        # Expected amount: (10000 / 100) * 0.1 = 10 shares
        expected_transactions = [
            {"ticker": "AAPL", "action": "BUY", "amount": 10, "allow_add": False, "price": 100.0}
        ]
        mock_ha.utför_flera_transaktioner.assert_called_with("test_bot", expected_transactions)

    @patch('main.ha')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_trade_suggestions_sell(self, mock_json_load, mock_open, mock_exists, mock_ha):
        """Test executing a SELL suggestion."""
        mock_exists.return_value = True
        # Portfolio has shares
        mock_json_load.return_value = {"fria_pengar": 1000, "aktier": {"AAPL": 5}}
        
        # Setup price data
        main.price_data = {}
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.iloc.__getitem__.return_value = 150.0
        main.price_data["AAPL"] = mock_df

        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"
        
        suggestions = {"AAPL": "SELL"}
        
        mock_ha.utför_flera_transaktioner.return_value = [main.ERROR_CODES.SUCCESS]
        
        main.trade_suggestions(mock_bot, suggestions)
        
        expected_transactions = [
            {"ticker": "AAPL", "action": "SELL", "amount": 5, "price": 150.0}
        ]
        mock_ha.utför_flera_transaktioner.assert_called_with("test_bot", expected_transactions)

    @patch('main.get_time_to_market_close')
    @patch('main.ha')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_trade_suggestions_buy_insufficient_funds(self, mock_json_load, mock_open, mock_exists, mock_ha, mock_time_close):
        """Test BUY suggestion with insufficient funds."""
        mock_exists.return_value = True
        # Portfolio has little money
        mock_json_load.return_value = {"fria_pengar": 500, "aktier": {}}
        
        mock_time_close.return_value = datetime.timedelta(minutes=30)
        
        main.price_data = {}
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.iloc.__getitem__.return_value = 100.0
        main.price_data["AAPL"] = mock_df
        
        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"
        mock_bot.risk = 0.1
        
        suggestions = {"AAPL": "BUY"}
        
        main.trade_suggestions(mock_bot, suggestions)
        
        # Should not call utför_flera_transaktioner due to insufficient funds
        mock_ha.utför_flera_transaktioner.assert_not_called()

    @patch('main.get_time_to_market_close')
    @patch('main.ha')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_trade_suggestions_buy_already_owned(self, mock_json_load, mock_open, mock_exists, mock_ha, mock_time_close):
        """Test BUY suggestion for already owned ticker (allow_add=False)."""
        mock_exists.return_value = True
        mock_json_load.return_value = {"fria_pengar": 10000, "aktier": {"AAPL": 5}}
        
        mock_time_close.return_value = datetime.timedelta(minutes=30)
        
        main.price_data = {}
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.iloc.__getitem__.return_value = 100.0
        main.price_data["AAPL"] = mock_df
        
        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"
        mock_bot.risk = 0.1
        
        suggestions = {"AAPL": "BUY"}
        
        main.trade_suggestions(mock_bot, suggestions)
        
        # Should not call due to already owned
        mock_ha.utför_flera_transaktioner.assert_not_called()

    @patch('main.get_time_to_market_close')
    @patch('main.ha')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_trade_suggestions_buy_market_closing(self, mock_json_load, mock_open, mock_exists, mock_ha, mock_time_close):
        """Test BUY suggestion when market is closing soon."""
        mock_exists.return_value = True
        mock_json_load.return_value = {"fria_pengar": 10000, "aktier": {}}
        
        # Market closing in 5 minutes (<10)
        mock_time_close.return_value = datetime.timedelta(minutes=5)
        
        main.price_data = {}
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.iloc.__getitem__.return_value = 100.0
        main.price_data["AAPL"] = mock_df
        
        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"
        mock_bot.risk = 0.1
        
        suggestions = {"AAPL": "BUY"}
        
        main.trade_suggestions(mock_bot, suggestions)
        
        # Should not call due to market closing
        mock_ha.utför_flera_transaktioner.assert_not_called()

    @patch('main.ha')
    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    @patch('json.load')
    def test_trade_suggestions_sell_not_owned(self, mock_json_load, mock_open, mock_exists, mock_ha):
        """Test SELL suggestion for unowned ticker."""
        mock_exists.return_value = True
        mock_json_load.return_value = {"fria_pengar": 1000, "aktier": {}}
        
        main.price_data = {}
        mock_df = MagicMock()
        mock_df.__getitem__.return_value.iloc.__getitem__.return_value = 150.0
        main.price_data["AAPL"] = mock_df

        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"
        
        suggestions = {"AAPL": "SELL"}
        
        main.trade_suggestions(mock_bot, suggestions)
        
        # Should not call due to not owned
        mock_ha.utför_flera_transaktioner.assert_not_called()

    @patch.object(inspect, 'signature')
    @patch('main.price_data')
    def test_run_bot_insufficient_data(self, mock_price_data, mock_signature):
        """Test run_bot skips when insufficient historical data."""
        mock_signature.return_value.parameters = {}  # No params, so uses price_data
        
        mock_bot = MagicMock()
        mock_bot.bot_name = "test_bot"
        mock_bot.required_period = 50
        mock_bot.tickers = ["AAPL"]
        
        # Mock price_data with insufficient length
        main.price_data = {"AAPL": [1] * 10}  # Only 10 points
        
        result_name, result_suggestions = main.run_bot(mock_bot)
        
        self.assertEqual(result_name, "test_bot")
        self.assertEqual(result_suggestions, {})  # Skipped

if __name__ == '__main__':
    unittest.main()