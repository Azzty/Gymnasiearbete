import json
from utils import PATH_TILL_PORTFÖLJER, PATH_TILL_LOGGAR
import os
import csv
import handla_aktie as ha
import datetime as dt
import yfinance as yf

price_data = {}

path = os.path.join(PATH_TILL_PORTFÖLJER, "macd_zeroline_bot.json")

def log_portfolio_value(bot_name:str, portfolio:dict) -> None:
    """
    Logs the total value of a bots portfolio
    
    :param bot_name: The name of the bot who owns the portfolio
    :type bot_name: str
    :param portfolio: A dict that should have a key 'aktier' that contains
    each ticker mapped to the amount owned, e.g NVDA: 100
    :type portfolio: dict
    """
    log_file_path = os.path.join(
        PATH_TILL_LOGGAR, "portfolio-logg-" + dt.date.today().strftime("%Y-%m-%d") + ".csv")
    with open(log_file_path, "a", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
        if os.path.getsize(log_file_path) == 0:
                            writer.writerow(
                                ["TIMESTAMP", "BOT", "VALUE"])
        portfolio_value = portfolio['fria_pengar']
        for t, amount in portfolio['aktier'].items():
            stock_price = 0.0
            if t not in price_data:
                print(t, "not in price_data, checking hämta_aktie")
                stock_price, ERROR_CODE = ha._get_stock_price(t)
                if stock_price is None:
                    print(f"Could not get price for {t}, skipping...")
                    continue
                print("returned price for", t, "was", stock_price)
            else:
                stock_price = price_data[t]["PRICE"].iloc[-1]
            portfolio_value += stock_price * amount
        print("Total value for", bot_name, "is", portfolio_value)
        writer.writerow([dt.datetime.now(), bot_name, portfolio_value])

with open(path, "r") as f:
    portfolio:dict = json.load(f)
    print(portfolio)
    print(type(portfolio))
    print(portfolio['aktier'].keys())
    log_portfolio_value("macd_zeroline_bot", portfolio)
    f.close()
