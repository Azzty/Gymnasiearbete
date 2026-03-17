import random
from datetime import datetime, timedelta
import csv

# Konfiguration
num_trade_opportunities = 1000
output_file_trades = r'C:\Users\antasp23\Documents\Programmering\Gymnasiearbete\dummy_trading_data.csv'
output_file_portfolio = r'C:\Users\antasp23\Documents\Programmering\Gymnasiearbete\dummy_portfolio_data.csv'

# Bot namn
bots = ['AlphaBot', 'BetaBot', 'GammaBot',
        'DeltaBot', 'EpsilonBot', 'ThetaBot']

# Tickers och startpriser
tickers = {
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

# Actions
actions = ['BUY', 'SELL']

# Starttid
current_time = datetime(2026, 1, 1, 9, 30, 0)  # 1 jan 2026, 09:30

# Håll koll på bot positions och priser för realism
bot_positions = {bot: {ticker: 0 for ticker in tickers} for bot in bots}
current_prices = tickers.copy()

bot_funds = {}
for bot in bots:
    bot_funds[bot] = 100_000

# Generera data_trades
data_trades = []
data_portfolios = []
header_trades = ['TIMESTAMP', 'BOT_NAME', 'TICKER',
                 'ACTION', 'AMOUNT', 'PRICE', 'TOTAL']
header_portfolio = ['TIMESTAMP', 'BOT', 'VALUE']

for i in range(num_trade_opportunities):
    # Choose some bots at random
    chosen_bots = random.choices(bots, k=random.randint(1, len(bots)))

    # Make each bot invest or sell
    for bot in chosen_bots:
        available_funds = bot_funds[bot]
        ticker = random.choice(list(tickers.keys()))
        action = random.choice(actions)
        price = current_prices[ticker]

        if action == 'BUY':
            # Invest 2% of available portfolio
            amount = int(0.02 * (available_funds / price))
            bot_positions[bot][ticker] += amount
            bot_funds[bot] -= price * amount
        else:
            # Sell everything
            amount = bot_positions[bot][ticker]
            bot_positions[bot][ticker] -= amount
            bot_funds[bot] += price * amount

        # Lägg till data_trades
        data_trades.append([
            current_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
            bot,
            ticker,
            action,
            amount,
            f"{price:.2f}",
            f"{(price * amount):.2f}"
        ])

        bot_portfolio_value = bot_funds[bot]
        for ticker, ticker_amount in bot_positions[bot].items():
            bot_portfolio_value += ticker_amount * current_prices[ticker]

        data_portfolios.append([
            current_time.strftime('%Y-%m-%d %H:%M:%S.%f'),
            bot,
            bot_portfolio_value
        ])

    # Update prices
    for ticker in current_prices:
        # +- 4 prisändring, med pytteliten vikt uppåt
        change = 1 + random.uniform(-0.04, 0.0405)
        current_prices[ticker] *= change

    # Lägg till tidsstämpel (5-60 sekunders mellanrum)
    time_increment = random.randint(5, 60)
    current_time += timedelta(seconds=time_increment)


# Spara till CSV
with open(output_file_trades, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header_trades)
    writer.writerows(data_trades)

with open(output_file_portfolio, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(header_portfolio)
    writer.writerows(data_portfolios)

print(f"Genererat {num_trade_opportunities} rader till {output_file_trades}")

# Visa första 20 raderna för kontroll
print("\nFörsta 20 raderna:")
print("-" * 80)
print(f"{'TIMESTAMP':<20} {'BOT':<10} {'TICKER':<6} {'ACTION':<6} {'AMOUNT':<6} {'PRICE':<8} {'TOTAL':<10}")
print("-" * 80)
for row in data_trades[:20]:
    print(
        f"{row[0]:<20} {row[1]:<10} {row[2]:<6} {row[3]:<6} {row[4]:<6} {row[5]:<8} {row[6]:<10}")

# Visa statistik
print(f"\nStatistik:")
print(f"Antal Bots: {len(bots)}")
print(f"Antal Tickers: {len(tickers)}")
print(f"Tidsspann: {data_trades[0][0]} till {data_trades[-1][0]}")
print(f"Totalt antal transaktioner: {len(data_trades)}")

# Räkna transaktioner per bot
bot_counts = {}
for row in data_trades:
    bot = row[1]
    bot_counts[bot] = bot_counts.get(bot, 0) + 1

print("\nTransaktioner per bot:")
for bot, count in sorted(bot_counts.items()):
    print(f"  {bot}: {count} transaktioner")

print("\nFinal ticker prices:")
print(current_prices)
