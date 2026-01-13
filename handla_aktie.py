"""
En kodfil för att hantera simulerade köp och säljning av aktier

`köp()` funktionen används för att köpa aktier

`sälj()` funktionen används för att sälja aktier
"""

import yfinance as yf
import json
import os
from utils import ERROR_CODES, PATH_TILL_PORTFÖLJER, PATH_TILL_PRISER, PATH_TILL_LOGGAR, thread_safe_print
import csv
import datetime
from math import floor
from typing import Tuple, Optional
import threading
import queue

TESTING = False
PRINT_TRANSACTIONS = False

log_queue = queue.Queue()
_log_thread = None


def log(bot_name, ticker, action, amount, price):
    """Logga en handling till dagens loggfil. Använder en dedikerad testfill om TESTING är True."""
    row = [datetime.datetime.now(), bot_name, ticker, action,
           amount, price, price * amount]
    log_queue.put(row)


def log_writer():
    """Worker function to write log messages"""
    log_file_path: str
    if TESTING:
        log_file_path = os.path.join(PATH_TILL_LOGGAR, "logg_test.csv")
    else:
        log_file_path = os.path.join(
            PATH_TILL_LOGGAR, "logg-" + datetime.date.today().strftime("%Y-%m-%d") + ".csv")
    with open(log_file_path, "a", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
        if os.path.getsize(log_file_path) == 0:
            writer.writerow(
                ["TIMESTAMP", "BOT", "TICKER", "ACTION", "AMOUNT", "PRICE", "TOTAL"])
        while True:
            row = log_queue.get()  # Yieldar tills något hamnar i kön
            if row is None:
                log_queue.task_done()  # Signal that the sentinel value is processed
                thread_safe_print("Logger thread closed.")
                break
            writer.writerow(row)
            log_queue.task_done()


def start_logger():
    """Starts the logging thread."""
    global _log_thread
    if _log_thread is None or not _log_thread.is_alive():
        # The thread is NOT a daemon, so the program will wait for it if it's still running.
        _log_thread = threading.Thread(target=log_writer)
        _log_thread.start()


def stop_logger():
    """Signals the logger to shut down and waits for it to finish."""
    thread_safe_print("Requesting logger shutdown...")
    log_queue.put(None)  # Send the sentinel value
    if _log_thread and _log_thread.is_alive():
        _log_thread.join()  # Wait for the thread to process the queue and terminate


def load_portfolio(bot_name: str) -> Optional[dict]:
    """Ladda portföljen för en given bot."""
    portfolio_path = os.path.join(PATH_TILL_PORTFÖLJER, bot_name + ".json")
    if not os.path.exists(portfolio_path):
        thread_safe_print(f"Portfölj för '{bot_name}' existerar inte.")
        return None

    try:
        with open(portfolio_path, 'r') as f:
            portfolio = json.load(f)
            return portfolio
    except (IOError, json.JSONDecodeError) as e:
        thread_safe_print(f"Kunde inte läsa portföljfilen: {e}")
        return None


def _validate_stock(ticker_str):
    """Validera ticker som str eller yf.Ticker."""
    stock = yf.Ticker(ticker_str)
    try:
        # Kontrollera om reg. marknadspris finns
        price = stock.info.get("regularMarketPrice")
        return price is not None
    except Exception:
        return False


def _get_stock_price(ticker) -> Tuple[Optional[float], ERROR_CODES]:
    """Funktion för att hämta det senaste priset av en aktie via dess ticker."""
    # try:
    if not _validate_stock(ticker):
        thread_safe_print(f"Kunde inte hitta ticker med namn {ticker}.")
        return None, ERROR_CODES.INVALID_TICKER

    file_path = os.path.join(PATH_TILL_PRISER, f"{ticker}.csv")
    last_line = ''
    price = 0
    price_file_exists = os.path.exists(file_path)
    if price_file_exists:
        with open(file_path, "rb") as f:

            # Read from the end of the file to get the last line
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            # Start reading backwards from the end
            offset = 2
            while offset <= file_size:
                f.seek(-offset, os.SEEK_END)
                char = f.read(1)
                if char == b'\n':
                    last_line = f.read()
                    break
                offset += 1
            last_line = last_line.decode()
    # If the last_line is empty or just a header, or if it's the header itself
    # (e.g., "TIME,PRICE,CHANGE_PERCENT,CHANGE,CUM_VOLUME"), then fetch from yfinance.
    if not price_file_exists or not last_line or "TIME" in last_line:
        thread_safe_print("File for", ticker, "price not found, attempting request from yfinance")
        stock = yf.Ticker(ticker)
        history = stock.history(period="1d", interval="1m")
        if history.empty:
            thread_safe_print(f"Kunde inte hitta historik för {ticker}.")
            return None, ERROR_CODES.HISTORY_NOEXIST
        price = history['Close'].iloc[-1]
    else:
        price = float(last_line.split(',')[1])

    return price, ERROR_CODES.SUCCESS

    # except Exception as e:
    #     # Något hände, whoopsie daisy
    #     thread_safe_print(f"Ett fel uppstod vid hämtning av pris för {ticker}: {e.with_traceback(e.__traceback__)}")
    #     return None, ERROR_CODES.PRICE_UNAVAILABLE


def köp(bot_name, ticker, antal, allow_add_to_position=True):
    """
    Försöker köpa ett specificerat antal aktier för en bot.

    Args:
        bot_name (str): Namnet på botten (och dess portföljfil).
        ticker (str): Aktiesymbolen att köpa (t.ex. 'AAPL').
        antal (int): Antalet aktier att köpa.
        allow_add_to_position (bool): Tillåt att köpa aktier du redan äger.

    Returns:
        enum: ERROR_CODE for the action
    """

    if antal <= 0:
        thread_safe_print("Antal måste vara ett positivt heltal.")
        return ERROR_CODES.INVALID_AMOUNT
    antal = floor(antal)  # Vi kan bara köpa ett helt antal aktier

    portfolio_path = os.path.join(PATH_TILL_PORTFÖLJER, bot_name + ".json")
    if not os.path.exists(portfolio_path):
        thread_safe_print(f"Portfölj för '{bot_name}' existerar inte.")
        return ERROR_CODES.PORTFOLIO_NOEXIST

    ticker = ticker.upper()
    price, error_code = _get_stock_price(ticker)
    if error_code != ERROR_CODES.SUCCESS:
        thread_safe_print(f"Kunde inte hämta pris för {ticker}. Köpet avbröts.")
        return error_code

    cost = price * antal

    try:
        with open(portfolio_path, 'r') as f:
            portfolio = json.load(f)
            if not allow_add_to_position and ticker in portfolio:
                return ERROR_CODES.ADD_SHARES_NOT_ALLOWED

        if portfolio.get('fria_pengar', 0) < cost:
            thread_safe_print(
                f"Inte tillräckligt med pengar. Behövs: {cost:.2f}, Tillgängligt: {portfolio.get('fria_pengar', 0):.2f}")
            return ERROR_CODES.INSUFFICIENT_AMOUNT

        # Uppdatera portfölj
        portfolio['fria_pengar'] -= cost
        if 'aktier' not in portfolio:
            portfolio['aktier'] = {}

        portfolio['aktier'][ticker] = portfolio['aktier'].get(
            ticker, 0) + antal

        # Spara uppdaterad portfölj
        with open(portfolio_path, 'w') as f:
            json.dump(portfolio, f, indent=4)

        thread_safe_print(f"{bot_name} köpte {antal} st {ticker} för ${cost:.2f}.")

        # Logga köpet
        log(bot_name, ticker, 'BUY', antal, price)

        return ERROR_CODES.SUCCESS

    except (IOError, json.JSONDecodeError) as e:
        thread_safe_print(f"Kunde inte läsa eller skriva till portföljfilen: {e}")
        return ERROR_CODES.JSON_ERROR


def sälj(bot_name: str, ticker: str, antal: int):
    """
    Försöker sälja ett specificerat antal aktier för en bot.

    Args:
        bot_name (str): Namnet på botten (och dess portföljfil).
        ticker (str): Aktiesymbolen att sälja (t.ex. 'AAPL').
        antal (int): Antalet aktier att sälja.

    Returns:
        enum: ERROR_CODE for the action
    """

    if antal <= 0:
        thread_safe_print("Antal måste vara postivt")
        return ERROR_CODES.INVALID_AMOUNT
    antal = floor(antal)

    portfolio_path = os.path.join(PATH_TILL_PORTFÖLJER, bot_name + ".json")
    if not os.path.exists(portfolio_path):
        thread_safe_print(f"Portfölj för '{bot_name}' existerar inte.")
        return ERROR_CODES.PORTFOLIO_NOEXIST

    ticker = ticker.upper()

    try:
        with open(portfolio_path, 'r') as f:
            portfolio = json.load(f)

        owned_shares = portfolio.get('aktier', {}).get(ticker, 0)
        if owned_shares == 0:
            thread_safe_print(f"Du äger inga aktier i {ticker}.")
            return ERROR_CODES.NO_SHARES

        # Om antal är större än max, sälj allt.
        shares_to_sell = min(antal, owned_shares)

        price, error_code = _get_stock_price(ticker)
        if error_code != ERROR_CODES.SUCCESS:
            thread_safe_print(f"Kunde inte hämta pris för {ticker}. Köpet avbröts.")
            return error_code
        income = price * shares_to_sell

        # Uppdatera värden i portfölj
        portfolio['fria_pengar'] += income
        portfolio['aktier'][ticker] -= shares_to_sell

        # Om alla aktier säljs, ta bort aktien från dicten.
        if portfolio['aktier'][ticker] == 0:
            del portfolio['aktier'][ticker]

        # Spara den uppdaterade portföljen
        with open(portfolio_path, 'w') as f:
            json.dump(portfolio, f, indent=4)

        thread_safe_print(f"{bot_name} sålde {shares_to_sell} st {ticker} för ${income:.2f}.")

        # Logga försäljningen
        log(bot_name, ticker, 'SELL', shares_to_sell, price)

        return ERROR_CODES.SUCCESS

    except (IOError, json.JSONDecodeError) as e:
        thread_safe_print(f"Kunde inte läsa eller skriva till portföljfilen: {e}")
        return ERROR_CODES.JSON_ERROR


def utför_flera_transaktioner(bot_name: str, transaktioner: list):
    """
    Utför en lista med transaktioner sekventiellt mot portföljen med endast en läsning och skrivning till fil.

    Args:
        bot_name (str): Namn på boten.
        transaktioner (list): Lista med dicts: {'ticker': str, 'action': 'BUY'|'SELL', 'amount': float, 'price': float (optional)}

    Returns:
        list: Lista med resultat (ERROR_CODES) för varje transaktion.
    """
    portfolio_path = os.path.join(PATH_TILL_PORTFÖLJER, bot_name + ".json")
    if not os.path.exists(portfolio_path):
        return [ERROR_CODES.PORTFOLIO_NOEXIST] * len(transaktioner)

    results = []

    try:
        with open(portfolio_path, 'r') as f:
            portfolio = json.load(f)

        portfolio_changed = False

        for t_data in transaktioner:
            ticker = t_data['ticker'].upper()
            action = t_data['action']
            amount = floor(t_data['amount'])

            if amount <= 0:
                results.append(ERROR_CODES.INVALID_AMOUNT)
                continue

            # Använd medskickat pris om det finns, annars hämta
            price = t_data.get('price')
            if price is None:
                price, error_code = _get_stock_price(ticker)
                if error_code != ERROR_CODES.SUCCESS:
                    results.append(error_code)
                    continue

            if action == "BUY":
                cost = price * amount
                if portfolio.get('fria_pengar', 0) < cost:
                    results.append(ERROR_CODES.INSUFFICIENT_AMOUNT)
                    continue

                allow_add = t_data.get('allow_add', False)
                if not allow_add and ticker in portfolio.get('aktier', {}):
                    results.append(ERROR_CODES.ADD_SHARES_NOT_ALLOWED)
                    continue

                portfolio['fria_pengar'] -= cost
                if 'aktier' not in portfolio:
                    portfolio['aktier'] = {}
                portfolio['aktier'][ticker] = portfolio['aktier'].get(
                    ticker, 0) + amount

                log(bot_name, ticker, 'BUY', amount, price)
                results.append(ERROR_CODES.SUCCESS)
                portfolio_changed = True
                if PRINT_TRANSACTIONS:
                    thread_safe_print(f"{bot_name} köpte {amount} st {ticker} för ${cost:.2f} (Batch).")

            elif action == "SELL":
                owned = portfolio.get('aktier', {}).get(ticker, 0)
                if owned == 0:
                    results.append(ERROR_CODES.NO_SHARES)
                    continue

                to_sell = min(amount, owned)
                income = price * to_sell

                portfolio['fria_pengar'] += income
                portfolio['aktier'][ticker] -= to_sell
                if portfolio['aktier'][ticker] == 0:
                    del portfolio['aktier'][ticker]

                log(bot_name, ticker, 'SELL', to_sell, price)
                results.append(ERROR_CODES.SUCCESS)
                portfolio_changed = True
                if PRINT_TRANSACTIONS:
                    thread_safe_print(f"{bot_name} sålde {to_sell} st {ticker} för ${income:.2f} (Batch).")

        if portfolio_changed:
            with open(portfolio_path, 'w') as f:
                json.dump(portfolio, f, indent=4)

        return results

    except (IOError, json.JSONDecodeError) as e:
        thread_safe_print(f"Batch error: {e}")
        return [ERROR_CODES.JSON_ERROR] * len(transaktioner)

## mini-Tester ##
# köp("test", "AAPL", 5)
# köp("test", "MSFT", 9)
# köp("test", "NVDA", 15)
# sälj("test", "AAPL", 3)
# sälj("test", "NVDA", 10)
# thread_safe_print(_get_stock_price("AAPL"))
