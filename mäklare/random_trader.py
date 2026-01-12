# Köper och säljer aktier slumpvalt
import random
import sys
import os

child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)
from utils import retrieve_data # nopep8

class RandomBot():
    """A trading bot that creates buy and sell signals randomly"""
    def __init__(self, bot_name, tickers:list[str], risk=0.02):
        self.bot_name = bot_name
        self.tickers = tickers
        self.risk = risk
        self.prev_prices = {}
    
    def find_options(self, price_data: dict | None = None):
        if price_data is None:
            price_data = retrieve_data(self.tickers, 1)
        suggestions = {}

        t:str
        for t in price_data.keys():
            # A perfect trading strategy
            suggestions[t] = "BUY" if random.random() >= 0.5 else "SELL"

        return suggestions

if __name__ == "__main__":
    bot = RandomBot("exempel", ["AAPL"])
    for _ in range(100):
        print(bot.find_options())