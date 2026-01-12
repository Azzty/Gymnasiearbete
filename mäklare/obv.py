"""Använder en OBV (On Balance Volume) analys för att skapa köp och sälj signaler"""

import sys
import os
import pandas_ta as ta

child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)

from utils import PATH_TILL_PRISER, PATH_TILL_PORTFÖLJER, retrieve_data  # nopep8


class OBVBot():
    """A trading bot that uses a OBV analysis.\n
    Buy when price is in uptrend and OBV and volume are above their moving averages.
    Sell when price reaches new low and OBV is below its moving average."""

    def __init__(self, bot_name, tickers: list[str], sample_long = 20, sample_short = 10, risk=0.02):
        self.bot_name = bot_name
        self.tickers = tickers
        # Since volume is relative to first datapoint, it will be nan. So we need to search 1 more minute
        # to make sure sample_length is guaranteed to have at least that many entries
        self.sample_length = sample_long + 1
        self.sample_long = sample_long
        self.sample_short = sample_short
        self.risk = risk
        self.states = {}

    def find_options(self, price_data: dict | None = None):
        """Finds and returns suggested actions for each stock in `self.tickers`"""
        if price_data is None:
            price_data = retrieve_data(self.tickers, self.sample_length)
        suggestions = {}

        for t, df in price_data.items():
            obv = ta.obv(df['PRICE'], df['VOLUME'])
            if obv is None or obv.empty:
                continue
            
            price = df['PRICE']
            volume = df['VOLUME']
            # Medelvärde på obv
            obv_ma = obv.rolling(self.sample_short).mean()
            # Kolla om priset är högsta på 20 minuter
            uptrend = price > price.rolling(self.sample_long).max().shift(1)

            # Köp om priset går uppåt och obv och volymen är högre än medelvärdet
            is_buy_signal = (
                uptrend.iloc[-1] & 
                (obv > obv_ma).iloc[-1] &
                (volume > volume.rolling(self.sample_long).mean()).iloc[-1]
            )
            # Sälj om priset nått ett nytt lågt och obv är under medelvärdet
            is_sell_signal = (
                (obv.iloc[-1] < obv_ma.iloc[-1]) &
                (price.iloc[-1] < price.rolling(self.sample_long).min().shift(1).iloc[-1])
            )
            if is_buy_signal: suggestions[t] = "BUY"
            elif is_sell_signal: suggestions[t] = "SELL"

        return suggestions


if __name__ == "__main__":
    bot = OBVBot("example", ["AAPL"], 9)
    print(bot.find_options())
