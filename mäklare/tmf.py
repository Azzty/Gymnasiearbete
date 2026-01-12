"""Använder Twiggs Money Flow för att ge köp/sälj signaler"""

import pandas
import os
import pandas_ta as ta
import sys

# Lägg till Gymnasiearbete mappen i path
# Detta gör att vi kan importera från andra mappar i projektet
child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)

from utils import PATH_TILL_PRISER, PATH_TILL_PORTFÖLJER, retrieve_data  # nopep8


class TMFBot():
    """A trading bot that uses a TMF indicator.\n
    `risk` is percentage of portfolio to spend on each purchase"""

    def __init__(self, bot_name: str, tickers: list[str], risk: float = 0.02, length=21):
        # Bot identification and portfolio name
        self.bot_name = bot_name
        # List of stock tickers to analyze
        self.tickers = tickers
        self.risk = risk
        self.length = length
        self.states = {}  # Håller koll på varje akties state

    def find_options(self, price_data: dict | None = None):
        """Finds and returns suggested actions for each stock in `self.tickers`"""
        if price_data is None:
            price_data = retrieve_data(self.tickers, self.length)
        suggestions = {}

        for t, df in price_data.items():
            if len(df['VOLUME']) < self.length:
                continue  # We dont have enough data

            # Initialize state for the ticker if not present
            if t not in self.states:
                self.states[t] = {'ad_sum': None,
                                  'vol_sum': None, 'prev_tmf': None}

            tmf = self.calculate_tmf(df, self.states[t])
            if tmf is None:
                continue

            prev_tmf = self.states[t]['prev_tmf']
            if prev_tmf is None:
                self.states[t]['prev_tmf'] = tmf  # Store first value
                continue

            if tmf > 0 and prev_tmf <= 0:
                suggestions[t] = "BUY"
            elif tmf < 0 and prev_tmf >= 0:
                suggestions[t] = "SELL"

            # Update previous tmf for next run
            self.states[t]['prev_tmf'] = tmf

        return suggestions

    def calculate_tmf(self, df: pandas.DataFrame, state: dict):
        # Formel hämtad från: https://www.incrediblecharts.com/indicators/twiggs_money_flow.php
        n = self.length

        TRH = max(df['HIGH'].iloc[-1], df['PRICE'].iloc[-2])
        TRL = min(df['LOW'].iloc[-1], df['PRICE'].iloc[-2])

        if TRH == TRL:
            return None  # Prevent division by zero

        if state['ad_sum'] is None:
            # Initial calculation using full series
            ad_series = ta.ad(df['HIGH'], df['LOW'], df['PRICE'], df['VOLUME'])
            state['ad_sum'] = ad_series.rolling(n).sum().iloc[-1]
            state['vol_sum'] = df['VOLUME'].rolling(n).sum().iloc[-1]

        # Efficiently update using an EMA-like approach for the sum
        ad_latest = (((df['PRICE'].iloc[-1] - TRL) - (TRH -
                     df['PRICE'].iloc[-1])) / (TRH - TRL)) * df['VOLUME'].iloc[-1]
        state['ad_sum'] = state['ad_sum'] * ((n-1)/n) + ad_latest
        state['vol_sum'] = state['vol_sum'] * ((n-1)/n) + df['VOLUME'].iloc[-1]

        if state['vol_sum'] == 0:
            return 0
        return state['ad_sum'] / state['vol_sum']
