# Om priset börjat gå upp, köp. Om priset börjat gå ner, sälj.

import sys
import os
from pandas import DataFrame

child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)

from utils import PATH_TILL_PRISER, PATH_TILL_PORTFÖLJER, retrieve_data  # nopep8


class UppDownBot():
    """A trading bot that buys if the price is going up, and sells if it is going down"""
    def __init__(self, bot_name, tickers: list[str], risk=0.02):
        self.bot_name = bot_name
        self.tickers = tickers
        self.risk = risk
        self.prev_prices = {}

    def find_options(self, price_data: dict | None = None):
        if price_data is None:
            price_data = retrieve_data(self.tickers, 1)
        suggestions = {}

        # Rensa bort tickers från minnet som inte längre är relevanta
        current_tickers = set(price_data.keys())
        self.prev_prices = {ticker: price for ticker, price in self.prev_prices.items() if ticker in current_tickers}


        t: str
        df: DataFrame
        for t, df in price_data.items():
            if t not in self.prev_prices:
                self.prev_prices[t] = df["PRICE"].iloc[-1]
                continue
            if df["PRICE"].iloc[-1] > self.prev_prices[t]:
                suggestions[t] = "BUY"
            elif df["PRICE"].iloc[-1] < self.prev_prices[t]:
                suggestions[t] = "SELL"
            self.prev_prices[t] = df["PRICE"].iloc[-1]

        return suggestions


if __name__ == "__main__":
    bot = UppDownBot("exempel", ["AAPL"])
    print(bot.find_options())
