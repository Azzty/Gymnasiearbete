"""Använder MACD strategi 1: Kolla när MACD- och signal-linjen korsar varandra"""

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


class MACDCrossoverBot():
    """A trading bot that uses an MACD Crossover strategy.\n
    `short_period` and `long_period` is the period for the short and long ema line respectively.
    `risk` is percentage of portfolio to spend on each purchase"""

    def __init__(self, bot_name: str, tickers: list[str], risk: float = 0.02, short_period: int = 9, long_period: int = 21):
        # Bot identification and portfolio name
        self.bot_name = bot_name
        # List of stock tickers to analyze
        self.tickers = tickers
        # The two periods for the short and long EMA periods
        self.short_period = short_period
        self.long_period = long_period
        self.risk = risk

    def find_options(self, price_data: dict | None = None):
        """Finds and returns suggested actions for each stock in `self.tickers`"""
        if price_data is None: price_data = retrieve_data(self.tickers, self.long_period)
        suggestions = {}

        base_date = datetime.datetime(1900, 1, 1)  # Startdatum för timestamps
        # Iterate through each stock's data to calculate EMAs and find signals.
        for t, df in price_data.items():
            macd = ta.macd(df["PRICE"])
            if macd is None or macd.empty: continue

            # The bot runs at the start of the minute (e.g., 14:30:00). We need to check if a crossover
            # happened in the minute that just completed (i.e., the 14:29:00 interval).
            target_timestamp = (pandas.Timestamp.combine(base_date, datetime.datetime.now(
            ).time()).floor("min") - pandas.Timedelta(minutes=1))
            # target_timestamp = pandas.Timestamp.fromisoformat("1900-01-01 19:50:00") # USE FOR DEBUG WITH TESTABELL3
            
            intersects = find_intersects(macd['MACD_12_26_9'], macd['MACDs_12_26_9'])
            # If a crossover just happened
            if intersects and [*intersects.keys()][-1] == target_timestamp:
                # Check the most recent crossover. 'over' means the short EMA crossed above the long EMA (a buy signal).
                # 'under' means the short EMA crossed below the long EMA (a sell signal).
                suggestions[t] = "BUY" if [
                    *intersects.values()][-1] == 'over' else "SELL"

        return suggestions

class MACDZerolineBot():
    """A trading bot that uses a MACD zero-line crossover strategy.\n
    `short_period` and `long_period` is the period for the short and long ema line respectively.
    `risk` is percentage of portfolio to spend on each purchase"""

    def __init__(self, bot_name: str, tickers: list[str], risk: float = 0.02, short_period: int = 9, long_period: int = 21):
        # Bot identification and portfolio name
        self.bot_name = bot_name
        # List of stock tickers to analyze
        self.tickers = tickers
        # The two periods for the short and long EMA periods
        self.short_period = short_period
        self.long_period = long_period
        self.risk = risk

    def find_options(self, price_data: dict | None = None):
        """Finds and returns suggested actions for each stock in `self.tickers`"""
        if price_data is None: price_data = retrieve_data(self.tickers, self.long_period)
        suggestions = {}

        base_date = datetime.datetime(1900, 1, 1)  # Startdatum för timestamps
        # Iterate through each stock's data to calculate EMAs and find signals.
        for t, df in price_data.items():
            macd = ta.macd(df["PRICE"])
            if macd is None or macd.empty: continue

            # The bot runs at the start of the minute (e.g., 14:30:00). We need to check if a crossover
            # happened in the minute that just completed (i.e., the 14:29:00 interval).
            target_timestamp = (pandas.Timestamp.combine(base_date, datetime.datetime.now(
            ).time()).floor("min") - pandas.Timedelta(minutes=1))
            # target_timestamp = pandas.Timestamp.fromisoformat("1900-01-01 19:50:00") # USE FOR DEBUG WITH TESTABELL3
            
            intersects = find_intersects(macd['MACD_12_26_9'])
            # If a crossover just happened
            if intersects and [*intersects.keys()][-1] == target_timestamp:
                # Check the most recent crossover. 'over' means the short EMA crossed above the long EMA (a buy signal).
                # 'under' means the short EMA crossed below the long EMA (a sell signal).
                suggestions[t] = "BUY" if [
                    *intersects.values()][-1] == 'over' else "SELL"

        return suggestions

def find_intersects(s0: pandas.Series, s1: pandas.Series | None = None):
    """Finds intersects between two pandas series or one series and the 0-line using vectorized operations.
    Returns a dict of time and type of intersection of all intersections.
    `s0` should be the shorter-period series.
    `s1` should be the longer-period series."""

    # Find where points are positive, 0 or negative, `pos` will be either 1, 0 or -1
    if s1 is not None:
        df = pandas.DataFrame({'s0': s0, 's1': s1}).dropna()
        df['pos'] = np.sign(df['s0'] - df['s1'])
    else:
        df = pandas.DataFrame({'s0': s0}).dropna()
        df['pos'] = np.sign(df['s0'])

    # Find points where the relationship changes from the previous point
    # A `diff` of  2 means `pos` changed from -1 to 1 (a "BUY" crossover).
    # A `diff` of -2 means `pos` changed from 1 to -1 (a "SELL" crossover).
    df['diff'] = df['pos'].diff()

    # Filter for the actual crossover points
    overs = df[df['diff'] == 2]
    unders = df[df['diff'] == -2]

    # Create dictionaries for each type of crossover {timestamp: 'over'}
    over_intersects = dict(zip(overs.index, ['over'] * len(overs)))
    under_intersects = dict(zip(unders.index, ['under'] * len(unders)))

    # Merge the two dictionaries
    all_intersects = {**over_intersects, **under_intersects}

    # Sort the combined dictionary by timestamp (the keys) and return it
    return dict(sorted(all_intersects.items()))


if __name__ == "__main__":
    from matplotlib import pyplot as plt
    
    # This block is for testing the script directly.
    aktie = 'TESTTABELL3'

    # Define paths for portfolio and price data
    portfölj = os.path.join(PATH_TILL_PORTFÖLJER, os.path.basename(__file__))
    priser = os.path.join(PATH_TILL_PRISER, aktie) + ".csv"
    
    bot1 = MACDCrossoverBot("exempel", [aktie])
    print(bot1.find_options())
    bot2 = MACDZerolineBot("exempel2", [aktie])
    print(bot2.find_options())

    df = retrieve_data([aktie], 5*26)[aktie]

    macd = ta.macd(df['PRICE'])

    plt.figure(1)
    plt.plot(df.index, df['PRICE'], label='Price')
    plt.legend()
    plt.figure(2)
    plt.plot(df.index, macd['MACD_12_26_9'], label='MACD')
    plt.plot(df.index, macd['MACDs_12_26_9'], label='Signal')
    plt.bar(df.index, macd['MACDh_12_26_9'], label='Histogram', width=0.0002)
    plt.axhline(0, color='grey', linestyle='--', linewidth=0.8)
    plt.legend()
    plt.show()
