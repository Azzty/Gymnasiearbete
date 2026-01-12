import unittest
from unittest.mock import patch, mock_open
import json
import os
from utils import ERROR_CODES
# The file to be tested
import handla_aktie as ha

class TestAktieHandel(unittest.TestCase):

    def setUp(self):
        """Set up a mock portfolio for each test."""
        self.bot_name = "test_bot"
        self.portfolio_path = os.path.join(ha.PATH_TILL_PORTFÖLJER, self.bot_name + ".json")
        self.mock_portfolio_data = {
            "fria_pengar": 10000.0,
            "aktier": {
                "AAPL": 10
            }
        }
        self.mock_portfolio_json = json.dumps(self.mock_portfolio_data)

    def _get_price_side_effect(self, ticker):
        """A side effect function for the mocked _get_stock_price."""
        prices = {
            "MSFT": 200.0,
            "AAPL": 150.0
        }
        price = prices.get(ticker.upper())
        if price is not None:
            return price, ERROR_CODES.SUCCESS
        return None, ERROR_CODES.INVALID_TICKER

    # --- Tests for köp() ---

    @patch('os.path.exists', return_value=False)
    def test_köp_portfolio_does_not_exist(self, mock_exists):
        """Test buying when the portfolio file doesn't exist."""
        # The function prints to stdout, which we suppress during tests
        with patch('builtins.print'):
            result = ha.köp(self.bot_name, "MSFT", 5) 
        self.assertEqual(result, ERROR_CODES.PORTFOLIO_NOEXIST)
        mock_exists.assert_called_once_with(self.portfolio_path)

    @patch.object(ha, '_get_stock_price', return_value=(None, ERROR_CODES.INVALID_TICKER))
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='{}')
    def test_köp_invalid_ticker(self, mock_file, mock_exists, mock_get_price):
        """Test buying a stock with an invalid ticker (price is None)."""
        with patch('builtins.print'):
            result = ha.köp(self.bot_name, "BADTICKER", 5) 
        self.assertEqual(result, ERROR_CODES.INVALID_TICKER)
        mock_get_price.assert_called_with("BADTICKER")
        mock_file().write.assert_not_called()

    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_köp_insufficient_funds(self, mock_file, mock_exists, mock_get_price):
        """Test buying a stock with not enough money."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        mock_get_price.side_effect = self._get_price_side_effect

        # Try to buy 100 MSFT shares at $200 each ($20,000) with only $10,000
        with patch('builtins.print'):
            result = ha.köp(self.bot_name, "MSFT", 100)
        
        self.assertEqual(result, ERROR_CODES.INSUFFICIENT_AMOUNT)
        mock_file.assert_called_once_with(self.portfolio_path, 'r')
        mock_file().write.assert_not_called()

    @patch('json.dump')
    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_köp_successful_new_stock(self, mock_file, mock_exists, mock_get_price, mock_json_dump):
        """Test successfully buying a stock not currently in the portfolio."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        mock_get_price.side_effect = self._get_price_side_effect

        with patch('builtins.print'):
            result = ha.köp(self.bot_name, "MSFT", 10) # Buy 10 MSFT @ $200
        
        self.assertEqual(result, ERROR_CODES.SUCCESS)
        
        # Verify file was opened for reading then writing
        mock_file.assert_any_call(self.portfolio_path, 'r')
        mock_file.assert_any_call(self.portfolio_path, 'w')

        # Check what was written to the file
        written_data = mock_json_dump.call_args[0][0]
        
        self.assertEqual(written_data['fria_pengar'], 8000.0) # 10000 - (10 * 200)
        self.assertEqual(written_data['aktier']['MSFT'], 10)
        self.assertEqual(written_data['aktier']['AAPL'], 10) # Unchanged

    @patch('json.dump')
    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_köp_successful_existing_stock(self, mock_file, mock_exists, mock_get_price, mock_json_dump):
        """Test successfully buying more of an existing stock."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        mock_get_price.side_effect = self._get_price_side_effect

        with patch('builtins.print'):
            result = ha.köp(self.bot_name, "AAPL", 5) # Buy 5 AAPL @ $150
        
        self.assertEqual(result, ERROR_CODES.SUCCESS)
        
        written_data = mock_json_dump.call_args[0][0]
        
        self.assertEqual(written_data['fria_pengar'], 9250.0) # 10000 - (5 * 150)
        self.assertEqual(written_data['aktier']['AAPL'], 15) # 10 + 5

    @patch('handla_aktie._get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_köp_negative_antal(self, mock_file, mock_exists, mock_get_price):
        """Test buying a negative number of shares."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        
        with patch('builtins.print'):
            result = ha.köp(self.bot_name, "MSFT", -5)
        self.assertEqual(result, ERROR_CODES.INVALID_AMOUNT)
        mock_get_price.assert_not_called() # Should fail before price check
        mock_file().write.assert_not_called()

    # --- Tests for sälj() ---

    @patch('os.path.exists', return_value=False)
    def test_sälj_portfolio_does_not_exist(self, mock_exists):
        """Test selling when the portfolio file doesn't exist."""
        with patch('builtins.print'):
            result = ha.sälj(self.bot_name, "AAPL", 5)
        self.assertEqual(result, ERROR_CODES.PORTFOLIO_NOEXIST)
        mock_exists.assert_called_once_with(self.portfolio_path)

    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_sälj_stock_not_owned(self, mock_file, mock_exists, mock_get_price):
        """Test selling a stock that is not in the portfolio."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        mock_get_price.side_effect = self._get_price_side_effect

        with patch('builtins.print'):
            result = ha.sälj(self.bot_name, "MSFT", 5)
        
        self.assertEqual(result, ERROR_CODES.NO_SHARES)
        mock_get_price.assert_not_called() # Should fail before price check
        mock_file().write.assert_not_called()

    @patch('json.dump')
    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_sälj_successful_partial(self, mock_file, mock_exists, mock_get_price, mock_json_dump):
        """Test successfully selling some shares of a stock."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        mock_get_price.side_effect = self._get_price_side_effect

        with patch('builtins.print'):
            result = ha.sälj(self.bot_name, "AAPL", 4) # Sell 4 of 10 AAPL @ $150
        
        self.assertEqual(result, ERROR_CODES.SUCCESS)
        
        written_data = mock_json_dump.call_args[0][0]
        
        self.assertEqual(written_data['fria_pengar'], 10600.0) # 10000 + (4 * 150)
        self.assertEqual(written_data['aktier']['AAPL'], 6) # 10 - 4

    @patch('json.dump')
    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_sälj_successful_all(self, mock_file, mock_exists, mock_get_price, mock_json_dump):
        """Test successfully selling all shares of a stock."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        mock_get_price.side_effect = self._get_price_side_effect

        with patch('builtins.print'):
            result = ha.sälj(self.bot_name, "AAPL", 10) # Sell all 10 AAPL @ $150
        
        self.assertEqual(result, ERROR_CODES.SUCCESS)
        
        written_data = mock_json_dump.call_args[0][0]
        
        self.assertEqual(written_data['fria_pengar'], 11500.0) # 10000 + (10 * 150)
        self.assertNotIn('AAPL', written_data['aktier'])

    @patch('json.dump')
    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_sälj_more_than_owned(self, mock_file, mock_exists, mock_get_price, mock_json_dump):
        """Test selling more shares than owned (should sell all)."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        mock_get_price.side_effect = self._get_price_side_effect

        with patch('builtins.print'):
            result = ha.sälj(self.bot_name, "AAPL", 20) # Try to sell 20, own 10
        
        self.assertEqual(result, ERROR_CODES.SUCCESS)
        
        written_data = mock_json_dump.call_args[0][0]
        
        self.assertEqual(written_data['fria_pengar'], 11500.0) # 10000 + (10 * 150)
        self.assertNotIn('AAPL', written_data['aktier'])

    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_sälj_negative_antal(self, mock_file, mock_exists, mock_get_price):
        """Test selling a negative number of shares."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        
        with patch('builtins.print'):
            result = ha.sälj(self.bot_name, "AAPL", -5)
        self.assertEqual(result, ERROR_CODES.INVALID_AMOUNT)
        mock_get_price.assert_not_called()
        mock_file().write.assert_not_called()

    @patch('json.dump')
    @patch.object(ha, '_get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_utför_flera_transaktioner(self, mock_file, mock_exists, mock_get_price, mock_json_dump):
        """Test executing multiple transactions in a batch."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        # Prices: MSFT=200, AAPL=150
        mock_get_price.side_effect = self._get_price_side_effect

        transactions = [
            {'ticker': 'MSFT', 'action': 'BUY', 'amount': 5, 'allow_add': True}, # Cost 1000
            {'ticker': 'AAPL', 'action': 'SELL', 'amount': 5}  # Income 750
        ]

        with patch('builtins.print'):
            results = ha.utför_flera_transaktioner(self.bot_name, transactions)
        
        self.assertEqual(results, [ERROR_CODES.SUCCESS, ERROR_CODES.SUCCESS])
        
        # Verify file opened read once, write once
        mock_file.assert_any_call(self.portfolio_path, 'r')
        mock_file.assert_any_call(self.portfolio_path, 'w')
        
        # Verify portfolio state
        written_data = mock_json_dump.call_args[0][0]
        # Start: 10000. Buy MSFT (5*200=1000) -> 9000. Sell AAPL (5*150=750) -> 9750.
        self.assertEqual(written_data['fria_pengar'], 9750.0)
        self.assertEqual(written_data['aktier']['MSFT'], 5)
        self.assertEqual(written_data['aktier']['AAPL'], 5) # Started with 10, sold 5

    @patch('handla_aktie._get_stock_price')
    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_utför_flera_transaktioner_with_provided_price(self, mock_file, mock_exists, mock_get_price):
        """Test batch transaction with pre-supplied price."""
        mock_file.return_value.read.return_value = self.mock_portfolio_json
        
        transactions = [
            {'ticker': 'MSFT', 'action': 'BUY', 'amount': 5, 'allow_add': True, 'price': 100.0}
        ]
        
        with patch('builtins.print'):
            ha.utför_flera_transaktioner(self.bot_name, transactions)
            
        # Should not call _get_stock_price because price is provided
        mock_get_price.assert_not_called()

if __name__ == '__main__':
    unittest.main()