"""Använder RSI för att ge köp/sälj signaler"""

import sys
import os
import pandas_ta as ta

# Lägg till Gymnasiearbete mappen i path
# Detta gör att vi kan importera från andra mappar i projektet
child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)

from utils import PATH_TILL_PORTFÖLJER, PATH_TILL_PRISER, retrieve_data  # nopep8


class RSIBot():
    """A trading bot that uses a Relative Strength Index (RSI) strategy.\n
    `length` is sample period, `upper` is sell bound, `lower` is buy bound,
    `risk` is percentage of available money to spend on each purchase"""

    def __init__(self, bot_name:str, tickers: list[str], length: int, upper: int, lower: int, risk=0.02):
        self.bot_name = bot_name
        self.tickers = tickers
        self.length = length
        self.upper = upper
        self.lower = lower
        self.risk = risk
        self.states = {}

    def find_options(self, price_data: dict | None = None):
        """Finds and returns suggested actions for each stock in `self.tickers`"""
        if price_data is None: price_data = retrieve_data(self.tickers, self.length)
        suggestions = {}

        for t, df in price_data.items():
            rsi = ta.rsi(df['PRICE'], self.length)
            if rsi is None or rsi.empty:
                continue

            # Make sure each stock has a state
            if t not in self.states:
                self.states[t] = 'NEUTRAL'

            # If rsi value goes above upper, enter SELL state. Once it drops back under upper, sell and go back to neutral
            # This is the same but reversed for BUY.
            if self.states[t] == 'NEUTRAL':
                if rsi.iloc[-1] > self.upper:
                    self.states[t] = 'SELL'
                elif rsi.iloc[-1] < self.lower:
                    self.states[t] = 'BUY'

            elif self.states[t] == 'BUY':
                if rsi.iloc[-1] > self.lower:
                    suggestions[t] = 'BUY'
                    self.states[t] = 'NEUTRAL'

            elif self.states[t] == 'SELL':
                if rsi.iloc[-1] < self.upper:
                    suggestions[t] = 'SELL'
                    self.states[t] = 'NEUTRAL'

        return suggestions


if __name__ == "__main__":
    from matplotlib import pyplot as plt
    # This block is for testing the script directly.
    aktie = 'TESTTABELL3'

    # Define paths for portfolio and price data
    portfölj = os.path.join(PATH_TILL_PORTFÖLJER, os.path.basename(__file__))
    priser = os.path.join(PATH_TILL_PRISER, aktie) + ".csv"

    df = retrieve_data([aktie], 21)[aktie]

    bot = RSIBot([aktie], 7, 70, 30)
    suggestions = bot.find_options()
    print(suggestions)
    
    rsi = ta.rsi(df['PRICE'], 9)

    # Plot the price and EMAs for visual verification
    plt.figure(1)
    plt.plot(df.index, df['PRICE'], label='Price')
    plt.figure(2)
    plt.plot(df.index, rsi, label='9 period RSI')
    plt.legend()
    plt.show()
