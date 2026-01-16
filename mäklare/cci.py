"""Använder Commodity Channel Index för att ge köp/sälj signaler"""

import os
from pandas_ta import hlc3, sma, mad

import sys

# Lägg till Gymnasiearbete mappen i path
# Detta gör att vi kan importera från andra mappar i projektet
child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)

from utils import PATH_TILL_PRISER, PATH_TILL_PORTFÖLJER, retrieve_data  # nopep8


class CCIBot():
    """A trading bot that uses a CCI indicator.\n
    `risk` is percentage of portfolio to spend on each purchase"""

    def __init__(self, bot_name: str, tickers: list[str], risk: float = 0.02, length = 20, lower=-100, upper=100):
        # Bot identification and portfolio name
        self.bot_name = bot_name
        # List of stock tickers to analyze
        self.tickers = tickers
        self.risk = risk
        self.lower = lower
        self.upper = upper
        self.length = length
        self.states = {}

    def find_options(self, price_data: dict | None = None):
        """Finds and returns suggested actions for each stock in `self.tickers`"""
        if price_data is None: price_data = retrieve_data(self.tickers, self.length)
        suggestions = {}

        # Iterate through each stock's data to calculate EMAs and find signals.
        for t, df in price_data.items():
            if df is None or df.empty or len(df) < self.length:
                continue
            # Manual CCI calculation because pandas_ta CCI is broken
            typical_price = hlc3(high=df['HIGH'], low=df['LOW'], close=df['PRICE'], talib=False)
            mean_typical_price = sma(typical_price, length=self.length, talib=False)
            mad_typical_price = mad(typical_price, length=self.length)

            if typical_price is None or mean_typical_price is None or mad_typical_price is  None:
                continue
            cci = (typical_price - mean_typical_price) / (0.015 * mad_typical_price)
                    
            if cci is None or cci.empty:
                continue
            # Make sure each stock has a state
            if t not in self.states:
                self.states[t] = 'NEUTRAL'

            # If cci value goes above upper, enter SELL state. Once it drops back under upper, sell and go back to neutral
            # This is the same but reversed for BUY.
            if self.states[t] == 'NEUTRAL':
                if cci.iloc[-1] > self.upper:
                    self.states[t] = 'SELL'
                elif cci.iloc[-1] < self.lower:
                    self.states[t] = 'BUY'

            elif self.states[t] == 'BUY':
                if cci.iloc[-1] > self.lower:
                    suggestions[t] = 'BUY'
                    self.states[t] = 'NEUTRAL'

            elif self.states[t] == 'SELL':
                if cci.iloc[-1] < self.upper:
                    suggestions[t] = 'SELL'
                    self.states[t] = 'NEUTRAL'

        return suggestions

if __name__ == "__main__":
    from matplotlib import pyplot as plt
    import pandas as pd
    # temp test
    bot = CCIBot("Test CCI Bot", ["AAPL"], risk=0.05)

    data: pd.DataFrame = retrieve_data(["AAPL"], length=100)
    print(data["AAPL"])
    print("Max:", data["AAPL"]['PRICE'].max(), "Min:", data["AAPL"]['PRICE'].min(), "Deviation:", data["AAPL"]['PRICE'].std())

     # data with enough points
    suggestions = bot.find_options(data)
    print("Suggestions:", suggestions)

    # Manual CCI calculation for verification
    typical_price = hlc3(high=data["AAPL"]['HIGH'], low=data["AAPL"]['LOW'], close=data["AAPL"]['PRICE'], talib=False)
    mean_typical_price = sma(typical_price, length=20, talib=False)
    mad_typical_price = mad(typical_price, length=20)


    cci = (typical_price - mean_typical_price) / (0.015 * mad_typical_price)

     # Plot CCI
    plt.plot(cci)
    plt.axhline(bot.upper, color='r', linestyle='--')
    plt.axhline(bot.lower, color='g', linestyle='--')
    plt.title("CCI Indicator for AAPL")
    plt.show()
