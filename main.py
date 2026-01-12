from zoneinfo import ZoneInfo
import datetime as dt
from hitta_100 import get_most_active_stocks
from hämta_aktiepriser import monitor_stocks, stop_monitoring
from mäklare import sma, ema, macd, obv, random_trader, rsi, uppner, stoch, cci, tmf
import handla_aktie as ha
import time
import os
import sys
import inspect
import json
import csv
from concurrent.futures import ThreadPoolExecutor

child_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(child_dir, '..'))
sys.path.append(parent_dir)

from utils import PATH_TILL_PRISER, PATH_TILL_PORTFÖLJER, PATH_TILL_LOGGAR, retrieve_data, ERROR_CODES  # nopep8

SHOW_SUGGESTIONS = False

tickers = get_most_active_stocks().split(" ")
# tickers = ["AAPL", "MSFT", "GOOG", "NVDA", "TSLA", "AMD", "META"]
max_period_length = -1  # Används för price_data caching, sätts i main
price_data: dict = {}  # Cache för prisdata
owned_tickers = set()  # Alla aktier som ägs av någon bot
top_active_tickers = set()  # Alla top 100 aktier


def us_market_open(now=None):
    if now is None:
        now = dt.datetime.now(ZoneInfo("America/New_York"))

    # Börsen är öppen mån–fre
    if now.weekday() >= 5:
        return False

    open_time = dt.time(9, 30)
    close_time = dt.time(16, 0)

    return open_time <= now.time() <= close_time


def get_time_to_market_close(now=None):
    if now is None:
        now = dt.datetime.now(ZoneInfo("America/New_York"))

    close_dt = dt.datetime.combine(
        now.date(),
        dt.time(16,0),
        tzinfo=now.tzinfo
    )

    return close_dt - now


def trade_suggestions(bot, bot_suggestions: dict):
    """Utför bottens rekommenderade åtgärd"""
    portfolio_path = os.path.join(PATH_TILL_PORTFÖLJER, bot.bot_name + ".json")
    
    # Ensure portfolio exists
    if not os.path.exists(portfolio_path):
        print(f"Portfölj för '{bot.bot_name}' existerar inte. Skapar en ny portfölj.")
        with open(portfolio_path, "w") as f:
            portfolio_setup = json.dumps({"fria_pengar": 100_000, "aktier": {}})
            f.write(portfolio_setup)

    # Load portfolio once for simulation
    try:
        with open(portfolio_path, "r") as f:
            portfolio = json.load(f)
    except (IOError, json.JSONDecodeError):
        print(f"Could not read portfolio for {bot.bot_name}")
        return

    current_cash = portfolio.get("fria_pengar", 0)
    owned_shares = portfolio.get("aktier", {})
    transactions = []

    for t, action in bot_suggestions.items():
        if action == "BUY":
            # Kolla om t är i top 100, annars skippa
            if t in owned_tickers and t not in top_active_tickers:
                print(f"{bot.bot_name} försökte köpa {t}, men den är inte top 100. Skippar...")
                continue
            # Kolla om ticker finns i pris_data, annars skippa
            if t not in price_data:
                print(f"WARNING: Could not get price data for {t} to buy, skipping...")
                continue
            # Köp inget nytt precis innan marknaden stänger
            if get_time_to_market_close() < dt.timedelta(minutes=10):
                continue
            # Check if already owned (since we pass allow_add=False)
            if t in owned_shares and owned_shares[t] > 0:
                continue

            price = price_data[t]["PRICE"].iloc[-1]
            amount = (current_cash / price) * bot.risk
            amount = int(amount)

            if amount > 0 and current_cash >= (amount * price):
                current_cash -= (amount * price)
                transactions.append({"ticker": t, "action": "BUY", "amount": amount, "allow_add": False, "price": price})

        elif action == "SELL":
            if t not in owned_shares or owned_shares[t] == 0:
                continue  # Vi har inget att sälja
            # Make sure we have price data before trying to access it
            if t not in price_data:
                print(f"WARNING: Could not get price data for {t} to sell, skipping...")
                continue
            amount = owned_shares[t]
            price = price_data[t]["PRICE"].iloc[-1]
            transactions.append({"ticker": t, "action": "SELL", "amount": amount, "price": price})

    if transactions:
        results = ha.utför_flera_transaktioner(bot.bot_name, transactions)
        
        for i, res in enumerate(results):
            t = transactions[i]["ticker"]
            if res not in [ERROR_CODES.SUCCESS, ERROR_CODES.ADD_SHARES_NOT_ALLOWED]:
                print(f"Problem uppstod när {bot.bot_name} skulle handla {t}. Felkod:{res.value}")
            
            if transactions[i]["action"] == "SELL" and res == ERROR_CODES.SUCCESS:
                if t in owned_tickers and not is_ticker_owned(t):
                    owned_tickers.remove(t)


def is_ticker_owned(ticker: str) -> bool:
    """
    Checks if a given ticker is currently owned by any bot.
    """
    for bot in bots:
        portfolio_path = os.path.join(
            PATH_TILL_PORTFÖLJER, bot.bot_name + ".json")
        if os.path.exists(portfolio_path):
            try:
                with open(portfolio_path, 'r') as f:
                    portfolio = json.load(f)
                    if 'aktier' in portfolio and ticker in portfolio['aktier'] and portfolio['aktier'][ticker] > 0:
                        return True
            except (IOError, json.JSONDecodeError) as e:
                print(
                    f"Warning: Could not read portfolio for {bot.bot_name} while checking ownership: {e}")
    return False


def get_all_owned_tickers(bots):
    """
    Scans all bot portfolios and returns a set of all unique stock tickers
    that are currently owned.
    """
    owned_tickers = set()
    for bot in bots:
        portfolio_path = os.path.join(
            PATH_TILL_PORTFÖLJER, bot.bot_name + ".json")
        if os.path.exists(portfolio_path):
            try:
                with open(portfolio_path, 'r') as f:
                    portfolio = json.load(f)
                    # Add all tickers from the 'aktier' dict to the set
                    if 'aktier' in portfolio:
                        owned_tickers.update(portfolio['aktier'].keys())
            except (IOError, json.JSONDecodeError) as e:
                print(
                    f"Warning: Could not read portfolio for {bot.bot_name}: {e}")
    return owned_tickers


def get_bot_owned_tickers(bot) -> set:
    """
    Scans a single bot's portfolio and returns a set of its owned stock tickers.
    """
    owned = set()
    portfolio_path = os.path.join(PATH_TILL_PORTFÖLJER, bot.bot_name + ".json")
    if os.path.exists(portfolio_path):
        try:
            with open(portfolio_path, 'r') as f:
                portfolio = json.load(f)
                if 'aktier' in portfolio:
                    # Add tickers that have more than 0 shares
                    owned.update(
                        {ticker for ticker, amount in portfolio['aktier'].items() if amount > 0})
        except (IOError, json.JSONDecodeError) as e:
            print(
                f"Warning: Could not read portfolio for {bot.bot_name} while getting its owned tickers: {e}")
    return owned


def run_bot(bot):
    """Worker funktion för att hämta suggestions och handla aktier efter suggestions"""
    print(
        f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Running bot '{bot.bot_name}'...")

    # Check if we have enough historical data for the bot
    if not all(len(price_data.get(t, [])) >= bot.required_period for t in bot.tickers):
        print(f"Skipping {bot.bot_name}: Not enough historical data (need {bot.required_period} points)")
        return bot.bot_name, {}

    bot_suggestions = {}

    # if possible, use already loaded price data instead of retrieving it again
    if len(inspect.signature(bot.find_options).parameters) == 1:
        bot_suggestions = bot.find_options(price_data)
    else:
        bot_suggestions = bot.find_options()

    # Execute trades
    trade_suggestions(bot, bot_suggestions)
    return bot.bot_name, bot_suggestions


def log_portfolio_value(bot_name:str, portfolio:dict) -> None:
    """
    Logs the total value of a bots portfolio
    
    :param bot_name: The name of the bot who owns the portfolio
    :type bot_name: str
    :param portfolio: A dict that should have a key 'aktier' that contains
    each ticker mapped to the amount owned, e.g NVDA: 100
    :type portfolio: dict
    """
    if portfolio is None:
        print(f"WARNING: Portfolio for {bot_name} is None, cannot log value.")
        return
    log_file_path = os.path.join(
        PATH_TILL_LOGGAR, "portfolio-logg-" + dt.date.today().strftime("%Y-%m-%d") + ".csv")
    with open(log_file_path, "a", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile, delimiter=',',
                            quotechar='"', quoting=csv.QUOTE_MINIMAL)
        if os.path.getsize(log_file_path) == 0:
                            writer.writerow(
                                ["TIMESTAMP", "BOT", "VALUE"])
        portfolio_value = portfolio['fria_pengar']
        for ticker, amount in portfolio['aktier'].items():
            stock_price = None
            if ticker in price_data:
                stock_price = price_data[ticker]["PRICE"].iloc[-1]
            else:
                stock_price, _ = ha._get_stock_price(ticker)
            if stock_price is not None:
                portfolio_value += stock_price * amount
            else:
                print(f"WARNING: Could not get price for {ticker} while logging portfolio value for {bot_name}, skipping...")
                continue
        writer.writerow([dt.datetime.now(), bot_name, portfolio_value])

def run_bots_periodically(bots, interval_seconds=60):
    global price_data, tickers, owned_tickers, top_active_tickers
    """
	Kör en lista bottar med jämna mellanrum.
	Siktar på att köra på i början av varje klockslag (e.g 15:30:00).
	"""
    print(
        f"Starting periodic bot execution every {interval_seconds} seconds. Press Ctrl+C to stop.")
    try:
        # Timer to check for new active stocks less frequently than every bot run
        ticker_update_interval = 60 * 15  # 15 minutes
        last_ticker_update = time.time()
        _start_attempts = 0
        _has_started = False
        while True:
            # Check if market is open
            if not us_market_open():
                if _has_started:
                    print("Market is closed. Stopping bot execution.")
                    break  # If program has already been run, then exit
                _start_attempts += 1
                time.sleep(60)
                if _start_attempts > 20:  # Vänta max 20 min
                    print("Market did not open. Program failed to start.")
                    break
            else:
                _has_started = True
            # 1. Beräkna nästa exakta körningstidpunkt
            # time.time() ger sekunder sedan "the epoch" (1970-01-01)
            # Vi använder modulo för att hitta hur många sekunder in i nästa intervall vi är
            # och subtraherar det från intervallet för att få tiden till nästa jämna körning.
            wait_time = interval_seconds - (time.time() % interval_seconds)
            print(
                f"Waiting for {wait_time:.2f} seconds until next run at {time.strftime('%H:%M:%S', time.localtime(time.time() + wait_time))}...", flush=True)
            time.sleep(wait_time)
            start_time = time.monotonic()

            # 2. Periodically update the list of monitored tickers
            current_time = time.time()
            if current_time - last_ticker_update > ticker_update_interval:
                print("\nChecking for new most active stocks...")
                new_tickers_to_monitor = set(
                    get_most_active_stocks().split(" "))

                # Update list of tickers to monitor
                if new_tickers_to_monitor != set(tickers):
                    print("Ticker pool has changed. Restarting monitor...")
                    print(f"Previously monitoring {len(tickers)} tickers.")
                    tickers = list(new_tickers_to_monitor)
                else:
                    print("Ticker pool is unchanged.")

                # Always refresh websockets to prevent timeout
                stop_monitoring()
                monitor_stocks(tickers)
                print(f"Monitoring restarted with {len(tickers)} tickers.")

                # Update tickers for each bot instance individually
                print("Updating individual bot ticker lists...")
                for bot in bots:
                    bot_owned = get_bot_owned_tickers(bot)
                    bot.tickers = list(top_active_tickers.union(bot_owned))

                last_ticker_update = current_time

            print("Running bots...", flush=True)
            suggestions = {}
            price_data = retrieve_data(tickers, max_period_length)
            # Kör alla bottar parallelt
            with ThreadPoolExecutor(max_workers=20) as executor:
                # Skapa processer
                futures = [
                    executor.submit(run_bot, bot)
                    for bot in bots
                ]

                # Spara resultat
                for future in futures:
                    bot_name, options = future.result()
                    suggestions[bot_name] = options
                    log_portfolio_value(bot_name, ha.load_portfolio(bot_name))

            if SHOW_SUGGESTIONS:
                # Log results
                if suggestions.values():
                    print("Suggestions found:")
                    # print("DEBUG: suggestions:", suggestions)
                    bot_suggestions: dict
                    for bot_name, bot_suggestions in suggestions.items():
                        if len(bot_suggestions) == 0:
                            print(bot_name, "had no suggestions")
                        else:
                            print(bot_name + ":")
                        for ticker, action in bot_suggestions.items():
                            print(f"  - {ticker}: {action}")
                else:
                    print("No trading suggestions at this time.")

            end_time = time.monotonic()
            execution_time = end_time - start_time
            print(f"Finished in {execution_time:.2f} seconds.", flush=True)

            # Om körningen tog längre tid än intervallet, hoppa direkt till nästa vänt-cykel
            # för att inte hamna i en "dödsspiral" där den försöker komma ikapp.
            if execution_time > interval_seconds:
                print(
                    f"WARNING: Execution time ({execution_time:.2f}s) exceeded interval ({interval_seconds}s). Skipping one cycle to catch up.", flush=True)

    except KeyboardInterrupt:
        print("\nStopping bot execution.")


# Säljer allt innehav hos alla bottar
def sell_all_bot_portfolios():
    for bot in bots:
        tickers = get_bot_owned_tickers(bot)
        transactions = []
        for ticker in tickers:
            # Handle case where price_data might not have this ticker
            if ticker in price_data:
                price = price_data[ticker]["PRICE"].iloc[-1]
            else:
                price, _ = ha._get_stock_price(ticker)
                if price is None:
                    continue
            transactions.append({'ticker': ticker, 'action': 'SELL', 'amount': 9999999, 'price': price})
        if transactions:
            ha.utför_flera_transaktioner(bot.bot_name, transactions)


if __name__ == "__main__":
    # Start logging thread
    ha.start_logger()
    
    # Starta datainsamlingen i bakgrunden
    monitor_stocks(tickers)

    # Skapa en lista över alla bots
    bots = []

    # Skapa en instans av din bot
    sma_bot = sma.SMABot("sma_crossover_bot", tickers,
                         short_period=9, long_period=21)
    ema_bot = ema.EMABot("ema_crossover_bot", tickers,
                         short_period=9, long_period=21)
    macd_cross_bot = macd.MACDCrossoverBot("macd_crossover_bot", tickers)
    # macd_zeroline_bot = macd.MACDZerolineBot("macd_zeroline_bot", tickers)
    obv_bot = obv.OBVBot("obv_bot", tickers, 9)
    random_bot = random_trader.RandomBot("random_bot", tickers)
    rsi_bot = rsi.RSIBot("rsi_bot", tickers, length=7, upper=70, lower=30)
    up_down_bot = uppner.UppDownBot("up_down_bot", tickers)
    stoch_bot = stoch.StochBot("stoch_bot", tickers, k_period=5)
    cci_bot = cci.CCIBot("cci_bot", tickers, length=14)
    tmf_bot = tmf.TMFBot("tmf_bot", tickers)

    # Set required warmup periods for each bot
    sma_bot.required_period = sma_bot.long_period
    ema_bot.required_period = ema_bot.long_period
    macd_cross_bot.required_period = macd_cross_bot.long_period
    obv_bot.required_period = obv_bot.sample_length
    random_bot.required_period = 1  # Minimal
    rsi_bot.required_period = rsi_bot.length
    up_down_bot.required_period = 2  # Minimal
    stoch_bot.required_period = stoch_bot.k_period
    cci_bot.required_period = cci_bot.length
    tmf_bot.required_period = tmf_bot.length

    # Lägg till alla bottar i bots
    bots.extend([sma_bot, ema_bot, macd_cross_bot,
                 obv_bot, random_bot, rsi_bot, up_down_bot, stoch_bot, cci_bot, tmf_bot])

    # Hitta längsta perioden bland bottarna, för price_data caching
    max_period_length = max(
        ema_bot.long_period, macd_cross_bot.long_period,
        obv_bot.sample_length, rsi_bot.length, stoch_bot.k_period,
        cci_bot.length, tmf_bot.length
    )

    # Kör boten periodiskt
    try:
        run_bots_periodically(bots, interval_seconds=60)
    except KeyboardInterrupt:
        print("Avbryter programmet...")
    finally:
        # Städa upp och stäng anslutningar när loopen avbryts
        stop_monitoring()
        sell_all_bot_portfolios()
        ha.stop_logger()
        print("Program exited successfully.")
