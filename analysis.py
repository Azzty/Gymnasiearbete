from typing import Generator, Any
from itertools import cycle

from matplotlib import pyplot as plt
import pandas
import datetime
from utils import PATH_TILL_LOGGAR
import os
import pandas_ta as ta
from heapq import *
import yfinance as yf

DEBUG = False

# Amount of x in top lists
TOP_LIST_AMOUNT = 10

# The date of experiment start
START_DATE = datetime.datetime(2026, 1, 14)
# The date of experiment end
END_DATE = datetime.datetime(2026, 2, 27)

# ...existing code...

# consistent brandning
BOT_COLORS = {}
BOT_COLOR_CYCLE = cycle(plt.rcParams["axes.prop_cycle"].by_key()["color"])


def get_bot_color(bot_name: str):
    if bot_name not in BOT_COLORS:
        BOT_COLORS[bot_name] = next(BOT_COLOR_CYCLE)
    return BOT_COLORS[bot_name]


# Aktivera interaktivt läge för pyplot
plt.ion()

# Startpriser
DUMMY_STARTING_VALUES = {
    'AAPL': 150.00,   # Apple
    'GOOG': 200.00,  # Google/Alphabet
    'MSFT': 300.00,   # Microsoft
    'AMZN': 120.00,   # Amazon
    'TSLA': 250.00,   # Tesla
    'META': 350.00,   # Meta/Facebook
    'NVDA': 500.00,   # NVIDIA
    'BTC': 4500.00,  # Bitcoin (krypto)
    'ETH': 300.00,   # Ethereum
    'SPY': 450.00     # S&P 500 ETF
}
DUMMY_FINAL_VALUES = {'AAPL': 171.2832967940381, 'GOOG': 259.97188293254936, 'MSFT': 98.04125817658932, 'AMZN': 180.88381869352773, 'TSLA': 338.61359905989997,
                      'META': 452.1814975395702, 'NVDA': 803.1929625208066, 'BTC': 6551.219884069063, 'ETH': 174.06969585918006, 'SPY': 316.14223353975086}

# Riktiga startpriser (OPEN) från 14 januari 2026
REAL_STARTING_VALUES = {
    'S&P 500': 6_969.46,
    'NASDAQ Composite': 23_693.97
}
# Riktiga slutpriser (CLOSE) från 27 februari 2026
REAL_FINAL_VALUES = {
    'S&P 500': 6_878.04,
    'NASDAQ Composite': 22_667.03
}

# Figurnummer för de olika graferna
bot_fig = 1
total_trade_fig = 2
port_fig = 3

# Amount of times sold quantity did not match bought quantity
total_quantity_discrapencies = 0
# Amount of profitable trades for each bot
trades_profit_by_bot = {}
# Amount of unprofitable trades for each bot
trades_loss_by_bot = {}
# Top x most profitable trades
most_profitable_trades = []
# Top x highest losses on trades
least_profitable_trades = []
# Profit per ticker per bot
ticker_profit_by_bot = {}

dummy_returns_ratio = [
    DUMMY_FINAL_VALUES[t] / DUMMY_STARTING_VALUES[t]
    for t in DUMMY_STARTING_VALUES
]
real_returns_ratio = [
    REAL_FINAL_VALUES[t] / REAL_STARTING_VALUES[t]
    for t in REAL_STARTING_VALUES
]


def update_performance_metrics(path_to_log_file: str):
    global total_quantity_discrapencies

    """Finds all completed trades in a log file and calculates the total return of those trades.
    Returns the total return as a float."""
    total_return = {}  # Total return from all completed trades for each bot
    bot_trades = {}  # Håller koll på vilka trades som gjorts av vilka bottar
    _positions = {}  # Håller koll på öppna positioner per aktie per bot
    try:
        with open(path_to_log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Log file {path_to_log_file} not found.")
        return bot_trades, total_return

    for line_nr, line in enumerate(lines):
        # Line template: <timestamp>,<bot_name>,<ticker>,<action>,<amount>,<price>,<total>
        # Example line: "2026-01-12 18:44:01.019202,random_bot,MARA,BUY,157,10.6369,1669.9933"

        parts = line.strip().split(',')
        if len(parts) < 7 or line_nr == 0:
            continue  # Broken line or header
        timestamp = datetime.datetime.strptime(
            parts[0], "%Y-%m-%d %H:%M:%S.%f")
        bot_name = parts[1]
        ticker = parts[2]
        action = parts[3]
        quantity = int(parts[4])
        price = float(parts[5])
        total = float(parts[6])

        # Create columns if they don't exist
        if bot_name not in bot_trades:
            bot_trades[bot_name] = []
        if bot_name not in _positions:
            _positions[bot_name] = {}
        if bot_name not in total_return:
            total_return[bot_name] = 0.0
        # if bot_name not in most_profitable_trades:
        #     most_profitable_trades[bot_name] = []
        # if bot_name not in least_profitable_trades:
        #     least_profitable_trades[bot_name] = []
        if bot_name not in ticker_profit_by_bot:
            ticker_profit_by_bot[bot_name] = {}
        if ticker not in ticker_profit_by_bot[bot_name]:
            ticker_profit_by_bot[bot_name][ticker] = 0

        if not total_trade_per_timestamp.get(timestamp.timestamp()):
            total_trade_per_timestamp[timestamp.timestamp()] = 0
        total_trade_per_timestamp[timestamp.timestamp(
        )] += total

        if action == "BUY":
            if ticker not in _positions[bot_name]:
                _positions[bot_name][ticker] = []
            # Spara köpt kvantitet och pris
            _positions[bot_name][ticker].append((quantity, price))
        elif action == "SELL":
            if ticker in _positions[bot_name] and _positions[bot_name][ticker]:
                total_invested = 0.0

                # Find total bought shares across all buys
                while len(_positions[bot_name][ticker]) > 0:
                    qty, prc = _positions[bot_name][ticker].pop()
                    total_invested += prc * qty

                if total_invested == 0:
                    continue

                # Calculate final return (price is sell price)
                trade_return = price * quantity - total_invested
                total_return[bot_name] += trade_return
                if trade_return > 0:
                    if not bot_name in trades_profit_by_bot:
                        trades_profit_by_bot[bot_name] = []
                    trades_profit_by_bot[bot_name].append(
                        {'ticker': ticker, 'profit': trade_return})

                    # Store n most profitable trades
                    update_top_trades(timestamp, bot_name,
                                      ticker, trade_return)
                else:
                    if not bot_name in trades_loss_by_bot:
                        trades_loss_by_bot[bot_name] = []
                    trades_loss_by_bot[bot_name].append(
                        {'ticker': ticker, 'loss': trade_return})
                    # Store n least profitable trades
                    update_worst_trades(timestamp, bot_name,
                                        ticker, trade_return)

                # Uppdatera profits per ticker
                ticker_profit_by_bot[bot_name][ticker] += trade_return

                bot_trades[bot_name].append(
                    (timestamp, ticker, total_invested, price, quantity, trade_return))

    return bot_trades, total_return


def update_worst_trades(timestamp, bot_name, ticker, trade_return):
    if len(least_profitable_trades) < TOP_LIST_AMOUNT:
        least_profitable_trades.append(
            [bot_name, ticker, timestamp, trade_return])
    else:
        max_val = -1*2**32
        index_to_pop = None
        for i, arr in enumerate(least_profitable_trades):
            if arr[3] > max_val:
                max_val = arr[3]
                index_to_pop = i
        if trade_return < max_val:
            least_profitable_trades.pop(index_to_pop)
            least_profitable_trades.append(
                [bot_name, ticker, timestamp, trade_return])


def update_top_trades(timestamp, bot_name, ticker, trade_return):
    if len(most_profitable_trades) < TOP_LIST_AMOUNT:
        most_profitable_trades.append(
            [bot_name, ticker, timestamp, trade_return])
    else:
        min_val = 2**32-1
        index_to_pop = None
        for i, arr in enumerate(most_profitable_trades):
            if arr[3] < min_val:
                min_val = arr[3]
                index_to_pop = i
        if trade_return > min_val:
            most_profitable_trades.pop(index_to_pop)
            most_profitable_trades.append(
                [bot_name, ticker, timestamp, trade_return])

# Hämtar nästa par av loggfiler från loggar


def get_next_log_file() -> Generator[str, Any, None]:
    date = START_DATE
    _fetch_attempts = 0
    while True:
        cur_log_file = os.path.join(
            PATH_TILL_LOGGAR, "logg-" + date.strftime("%Y-%m-%d") + ".csv")

        if not os.path.exists(cur_log_file):
            # print("Fetch failed for date:", date.date())
            # No logs on weekends.
            # Search max 1 week with no logs, else give up
            if _fetch_attempts < 7:
                date += datetime.timedelta(days=1)
                _fetch_attempts += 1
                continue
            else:
                break
        else:
            _fetch_attempts = 0  # Reset count on success

        yield cur_log_file
        date += datetime.timedelta(days=1)


def get_next_portfolio_file() -> Generator[str, Any, None]:
    date = START_DATE
    _fetch_attempts = 0
    while True:
        cur_port_file = os.path.join(
            PATH_TILL_LOGGAR, "portfolio-logg-" + date.strftime("%Y-%m-%d") + ".csv")

        if not os.path.exists(cur_port_file):
            # print("Fetch failed for date:", date.date())
            # No logs on weekends.
            # Search max 1 week with no logs, else give up
            if _fetch_attempts < 7:
                date += datetime.timedelta(days=1)
                _fetch_attempts += 1
                continue
            else:
                break
        else:
            _fetch_attempts = 0  # Reset count on success

        yield cur_port_file
        date += datetime.timedelta(days=1)


def plot_trade_activity(trades) -> None:
    for bot in trades:
        timestamps = []
        values = []

        # print(f"Bot: {bot}")
        for trade in trades[bot]:
            # print(trade)
            timestamp, ticker, total_invested, sell_price, quantity, trade_return = trade

            if isinstance(timestamp, str):
                dt = datetime.datetime.strptime(
                    timestamp, '%Y-%m-%d %H:%M:%S.%f')
            else:
                dt = timestamp

            dt: datetime.datetime
            timestamps.append(dt)
            values.append(total_invested)
            # print(
            #     f"Ticker: {ticker}, Bought at: {buy_price}, Sold at: {sell_price}, Quantity: {quantity}, Return: {trade_return:.2f}")
        plt.figure(bot_fig)
        plt.plot(timestamps, values, label=bot, color=get_bot_color(bot))
        plt.pause(0.1)  # Uppdatera graf


def plot_portfolio_values(port_file, freq='5min'):
    bot_portfolio_values = {}
    with open(port_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        first_timestamp = None
        final_timestamp = None

        for line_nr, line in enumerate(lines):
            parts = line.split(",")
            if len(parts) < 3 or line_nr == 0:
                continue  # Broken line or header

            timestamp = datetime.datetime.strptime(
                parts[0], "%Y-%m-%d %H:%M:%S.%f")
            # Ensure timestamp is at start of minute
            timestamp.replace(second=0, microsecond=0)

            bot = parts[1]
            value = float(parts[2])

            if not first_timestamp:
                first_timestamp = timestamp
            final_timestamp = timestamp

            if not bot in bot_portfolio_values:
                bot_portfolio_values[bot] = {}

            bot_portfolio_values[bot][timestamp] = value

    for bot, portfolio in bot_portfolio_values.items():
        timestamps = []
        values = []
        for timestamp, value in portfolio.items():
            timestamps.append(timestamp)
            values.append(value)
        plt.figure(port_fig)
        plt.plot(timestamps, values, label=bot)
        plt.pause(0.01)  # Uppdatera graf
    return first_timestamp, final_timestamp


if __name__ == "__main__":
    # List all bot names based on JSON files in the portfolios directory
    # bot_names = [name for name in os.listdir(PATH_TILL_PORTFÖLJER) if os.path.isfile(
    #     os.path.join(PATH_TILL_PORTFÖLJER, name)) and name.endswith('.json')]

    # TODO: More statistics:
    # - Portfolio value over time by bot -- DONE
    # - Average win/loss per trade per bot -- DONE
    # - Percentage of trades profitable -- DONE
    # - Most bought ticker
    # - Most profitable ticker -- DONE
    # - buy-and-hold to compare -- DONE
    # - Biggest win(s) -- DONE
    # - Biggest Loss(es) -- DONE

    total_trade_per_timestamp = {}

    if DEBUG:
        trades, total_return = update_performance_metrics(
            r"C:\Users\antasp23\Documents\Programmering\Gymnasiearbete\dummy_trading_data.csv")

        # fig, (bot_fig, total_trade_fig, port_fig) = plt.subplots(3)

        plot_trade_activity(trades)

        first_timestamp, final_timestamp = plot_portfolio_values(
            r"C:\Users\antasp23\Documents\Programmering\Gymnasiearbete\dummy_portfolio_data.csv")

        buy_and_hold_return = 100_000 * \
            (sum(dummy_returns_ratio) / len(dummy_returns_ratio)) - 100_000

        plt.plot([first_timestamp, final_timestamp], [
                 100_000, 100_000 + buy_and_hold_return], label="Buy and hold reference", linewidth=2)

    # LÄS IGENOM FILER
    else:
        # Plotta utveckling från alla logg-filer

        # Hämta S&P 500 och NASDAQ Composite för jämförelse (end är exlusivt, så +1 dag)
        index_data = yf.download(
            ['^SPX', '^NDX'], start=START_DATE, end=END_DATE + datetime.timedelta(days=1), interval="1h")

        # Align index data with portfolio data by using the same time index
        spx_normalised = index_data['Close']['^SPX'] / \
            index_data['Close']['^SPX'].iloc[0] * 100_000
        ndx_normalised = index_data['Close']['^NDX'] / \
            index_data['Close']['^NDX'].iloc[0] * 100_000

        # Remove timezone information to match portfolio dataframe index
        spx_normalised.index = spx_normalised.index.tz_localize(None)
        ndx_normalised.index = ndx_normalised.index.tz_localize(None)

        # Compare bot performance to S&P 500 on day-by-day basis
        bot_vs_spx = {}
        for f in get_next_log_file():
            trades, total_return = update_performance_metrics(f)

            # Extract the date from the log filename
            filename = os.path.basename(f)
            date_str = filename.replace("logg-", "").replace(".csv", "")
            log_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

            for bot in total_return:
                # Calculate bot daily returns and compare to S&P 500
                bot_daily_return = total_return[bot]
                # Get S&P 500 return for this specific date
                # Filter data for this day
                day_mask = spx_normalised.index.date == log_date
                day_data = spx_normalised[day_mask]

                if len(day_data) > 1:
                    start_price = day_data.iloc[0]
                    end_price = day_data.iloc[-1]
                    spx_return = end_price - start_price

                    if bot not in bot_vs_spx:
                        bot_vs_spx[bot] = {"wins": 0, "losses": 0}

                    if bot_daily_return > spx_return:
                        # Bot outperformed S&P 500
                        bot_vs_spx[bot]["wins"] += 1
                    else:
                        bot_vs_spx[bot]["losses"] += 1

        print("------- Winrate -------")
        for bot in bot_vs_spx:
            wins = bot_vs_spx[bot]["wins"]
            losses = bot_vs_spx[bot]["losses"]
            print(bot, "Wins:", wins, "Losses:", losses)
            print("Effective winrate:", str(
                100 * wins / (wins + losses)) + "%", "\n-----")

        port_df = pandas.concat(
            [
                pandas.read_csv(
                    f,
                    parse_dates=["TIMESTAMP"]
                )
                for f in get_next_portfolio_file()
            ],
            ignore_index=True
        )

        port_df.sort_values("TIMESTAMP", inplace=True)
        # port_df["TIMESTAMP"] = port_df['TIMESTAMP'].dt.floor("1h")
        port_df = port_df[port_df["TIMESTAMP"].dt.time < datetime.time(21)]

        port_df = port_df.pivot(
            index="TIMESTAMP", columns="BOT", values="VALUE"
        ).resample("1h").last().dropna(how="all")

        # Reindex both to ensure they use the same timestamps
        # Use the portfolio dataframe's index as the reference
        spx_aligned = spx_normalised.reindex(port_df.index, method='ffill')
        ndx = ndx_normalised.reindex(port_df.index, method='ffill')

        plt.figure(port_fig)
        for col in port_df.columns:
            # if col == 'up_down_bot':
            #     continue  # Temporarily skip up_down_bot cause it sucked
            plt.plot(range(len(port_df)),
                     port_df[col], label=col, color=get_bot_color(col))

        # Plot index funds using the same x-axis alignment
        plt.plot(range(len(port_df)), spx_aligned.values, label="S&P 500",
                 linewidth=2, zorder=9, color="#FF0000")
        plt.plot(range(len(port_df)), ndx.values, label="NASDAQ 100",
                 linewidth=2, zorder=9, color='#0000FF')
        # Annotate S&P 500 line
        plt.annotate('S&P 500', xy=(len(port_df)-1, spx_aligned.values[-1]),
                     xytext=(len(port_df)+12, spx_aligned.values[-1] + 2000),
                     arrowprops=dict(facecolor='black', arrowstyle="-"))

        # Annotate NASDAQ 100 line
        plt.annotate('NASDAQ 100', xy=(len(port_df)-1, ndx.values[-1]),
                     xytext=(len(port_df)+12, ndx.values[-1] - 1000),
                     arrowprops=dict(facecolor='black', arrowstyle="-"))
        # Logga aktivitet
        log_df = pandas.concat(
            [
                pandas.read_csv(
                    f,
                    parse_dates=["TIMESTAMP"]
                )
                for f in get_next_log_file()
            ]
        )

        activity_df = log_df.pivot(
            index="TIMESTAMP", columns="BOT", values="TOTAL"
        ).resample("1h").sum(min_count=1).dropna(how="all")

        log_without_random = log_df.drop(
            log_df[log_df["BOT"] == "random_bot"].index)

        ticker_activity_df = log_without_random.pivot(
            index="TIMESTAMP", columns="TICKER", values="TOTAL"
        ).resample("1h").sum(min_count=1).dropna(how="all")

        plt.figure(bot_fig)
        for col in activity_df.columns:
            if col in ['random_bot', 'up_down_bot']:
                continue  # Get better view of activity
            plt.plot(range(len(activity_df)),
                     activity_df[col], label=col, color=get_bot_color(col))

    print("Total quantity discrapencies:", total_quantity_discrapencies)

    print("\nTop wins:")
    for tradedata in sorted(most_profitable_trades, key=lambda data: data[3], reverse=True):
        print(tradedata)

    print("\nTop losses:")
    for tradedata in sorted(least_profitable_trades, key=lambda data: data[3]):
        print(tradedata)

    print("\n---------- Wins and losses per bot ----------")
    for bot, wins in trades_profit_by_bot.items():
        print("--", bot, "--")
        wins_list = wins
        losses_list = trades_loss_by_bot[bot] if bot in trades_loss_by_bot else [
        ]

        total_wins = len(wins_list)
        total_losses = len(losses_list)
        total_trades = total_wins + total_losses

        print("Wins:", total_wins, "Losses:", total_losses)
        print("Win %:", 100 * total_wins /
              total_trades if total_trades > 0 else 0)

        # Calculate average win per winning trade
        if total_wins > 0:
            avg_win = sum(trade['profit'] for trade in wins_list) / total_wins
            print("Average win per winning trade:", f"{avg_win:.2f}")

        # Calculate average loss per losing trade
        if total_losses > 0:
            avg_loss = sum(trade['loss']
                           for trade in losses_list) / total_losses
            print("Average loss per losing trade:", f"{avg_loss:.2f}")

        # Calculate overall average return per trade
        if total_trades > 0:
            total_return_bot = sum(
                trade['profit'] for trade in wins_list) + sum(trade['loss'] for trade in losses_list)
            avg_return_per_trade = total_return_bot / total_trades
            print("Average return per trade:", f"{avg_return_per_trade:.2f}")

        print()

    ticker_profits = {}
    for bot in ticker_profit_by_bot:
        for ticker in ticker_profit_by_bot[bot]:
            if ticker not in ticker_profits:
                ticker_profits[ticker] = 0.0
            ticker_profits[ticker] += ticker_profit_by_bot[bot][ticker]

    print("-- Total profit per ticker: --")
    for ticker, profit in ticker_profits.items():
        print("ticker:", ticker, "profit", profit)

    # Bot, ticker, tid, profit
    items = sorted(total_trade_per_timestamp.items())

    tt_x = [datetime.datetime.fromtimestamp(k) for k, v in items]
    tt_y = [v for k, v in items]

    tt_df = pandas.DataFrame(
        {'datetime': tt_x, 'total_trade': tt_y})
    tt_df.set_index('datetime', inplace=True)
    tt_df = tt_df.resample('1h').sum(min_count=1).dropna(how="all")

    # Filter for business hours only (before 21:00)
    tt_df = tt_df[tt_df.index.time < datetime.time(21)]
    bar_width = 0.8

    plt.figure(total_trade_fig)
    plt.bar(range(len(tt_df)), tt_df['total_trade'], width=bar_width)
    sma_tt = ta.sma(tt_df['total_trade'], length=10)
    plt.plot(range(len(tt_df)), sma_tt,
             label='Genomsnittlig aktivitet (10 timmar)', color='r', linewidth=2)

    plt.figure(bot_fig)
    plt.xlabel('Tid (timmar)')
    plt.ylabel('Handelsvoylm')
    plt.title('Handelsaktivitet per bot över tid (utan random- och upp/ner botten)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    plt.figure(total_trade_fig)
    plt.xlabel('Tid (timmar)')
    plt.ylabel('Total handelvolym')
    plt.title('Total handelsvolym över tid')
    plt.legend()

    plt.figure(port_fig)
    plt.xlabel('Tid (timmar)')
    plt.ylabel('Portföljvärde (USD)')
    plt.title('Värdet av portföljer över tid')
    plt.legend()

    plt.ioff()
    plt.show()
