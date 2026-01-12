"""Använder korsniningar av två EMA kurvor för att ge köp/sälj signaler"""

import numpy as np
import pandas
import os
import pandas_ta as ta
import sys
import datetime

# Lägg till Gymnasiearbete mappen i path
# Detta gör att vi kan importera från andra mappar i projektet
child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)

from utils import PATH_TILL_PRISER, PATH_TILL_PORTFÖLJER, retrieve_data  # nopep8


class StochBot():
    """A trading bot that uses a stochastic indicator.\n
    `short_period` and `long_period` is the period for the short and long ema line respectively.
    `risk` is percentage of portfolio to spend on each purchase"""

    def __init__(self, bot_name: str, tickers: list[str], risk: float = 0.02, k_period: int = 14, d_period: int = 3, smooth_k: int = 3, lower_bound: int = 20, upper_bound: int = 80):
        # Bot identification and portfolio name
        self.bot_name = bot_name
        # List of stock tickers to analyze
        self.tickers = tickers
        self.risk = risk
        # Stochastic parameters
        self.k_period = k_period
        self.d_period = d_period
        self.smooth_k = smooth_k
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        # State management for each ticker
        self.states = {}

    def find_options(self, price_data: dict | None = None):
        """Finds and returns suggested actions for each stock in `self.tickers`"""
        # The stochastic oscillator needs a lookback period to calculate its values.
        # The default k_period is 14, so we need at least that many data points.
        if price_data is None:
            price_data = retrieve_data(self.tickers, self.k_period)
        suggestions = {}

        for t, df in price_data.items():
            stoch = ta.stoch(df['HIGH'], df['LOW'], df['PRICE'], k=self.k_period, d=self.d_period, smooth_k=self.smooth_k)
            if stoch is None or stoch.empty:
                continue

            # Default column names from pandas-ta are like 'STOCHk_14_3_3'
            k_col = f'STOCHk_{self.k_period}_{self.d_period}_{self.smooth_k}'
            d_col = f'STOCHd_{self.k_period}_{self.d_period}_{self.smooth_k}'

            if k_col not in stoch.columns or d_col not in stoch.columns:
                continue

            stoch_k = stoch[k_col]
            stoch_d = stoch[d_col]

            if t not in self.states:
                self.states[t] = 'NEUTRAL'

            k_now, d_now = stoch_k.iloc[-1], stoch_d.iloc[-1]
            k_prev, d_prev = stoch_k.iloc[-2], stoch_d.iloc[-2]

            # State: WAITING_FOR_BUY_CROSS (Oversold zone)
            if self.states[t] == 'WAITING_FOR_BUY_CROSS':
                # Check for a bullish crossover (%K crosses above %D)
                if k_now > d_now and k_prev <= d_prev:
                    suggestions[t] = 'BUY'
                    self.states[t] = 'NEUTRAL'
                # If it leaves the oversold zone without a cross, reset state
                elif k_now > self.lower_bound and d_now > self.lower_bound:
                    self.states[t] = 'NEUTRAL'

            # State: WAITING_FOR_SELL_CROSS (Overbought zone)
            elif self.states[t] == 'WAITING_FOR_SELL_CROSS':
                # Check for a bearish crossover (%K crosses below %D)
                if k_now < d_now and k_prev >= d_prev:
                    suggestions[t] = 'SELL'
                    self.states[t] = 'NEUTRAL'
                # If it leaves the overbought zone without a cross, reset state
                elif k_now < self.upper_bound and d_now < self.upper_bound:
                    self.states[t] = 'NEUTRAL'

            # State: NEUTRAL
            elif self.states[t] == 'NEUTRAL':
                # If both lines enter the oversold zone, prepare for a buy signal
                if k_now < self.lower_bound and d_now < self.lower_bound:
                    self.states[t] = 'WAITING_FOR_BUY_CROSS'
                # If both lines enter the overbought zone, prepare for a sell signal
                elif k_now > self.upper_bound and d_now > self.upper_bound:
                    self.states[t] = 'WAITING_FOR_SELL_CROSS'

        return suggestions


if __name__ == "__main__":
    from matplotlib import pyplot as plt
    
    # This block is for testing the script directly.
    aktie = 'AAPL'

    # Define paths for portfolio and price data
    portfölj = os.path.join(PATH_TILL_PORTFÖLJER, os.path.basename(__file__))
    priser = os.path.join(PATH_TILL_PRISER, aktie) + ".csv"

    price_data = retrieve_data([aktie], 21)
    if not price_data or aktie not in price_data:
        print(f"Could not retrieve data for {aktie}")
        exit()
    df = price_data[aktie]

    stoch = ta.stoch(df['HIGH'], df['LOW'], df['PRICE'])
    stoch_k = stoch['STOCHk_14_3_3']
    stoch_d = stoch['STOCHd_14_3_3']

    # Plot the price and EMAs for visual verification
    plt.figure(1)
    plt.plot(df.index, stoch_k, label='STOCHk_14_3_3')
    plt.plot(df.index, stoch_d, label='STOCHd_14_3_3')
    plt.legend()
    plt.figure(2)
    plt.plot(df.index, stoch['STOCHh_14_3_3'], label='STOCHh_14_3_3')
    plt.legend()
    plt.show()
