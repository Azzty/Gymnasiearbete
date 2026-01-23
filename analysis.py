from matplotlib import pyplot as plt
import pandas
import numpy as np
import datetime
from utils import PATH_TILL_LOGGAR, PATH_TILL_PORTFÖLJER
import os

def find_trades_of_bots(name_of_log_file: str):
	"""Finds all completed trades in a log file and calculates the total return of those trades.
	Returns the total return as a float."""
	log_path = PATH_TILL_LOGGAR + os.sep + name_of_log_file
	total_return = 0.0  # Total return from all completed trades
	bot_trades = pandas.DataFrame() # Håller koll på vilka trades som gjorts av vilka bottar
	_positions = pandas.DataFrame()  # Håller koll på öppna positioner per aktie
	try:
		with open(log_path, 'r', encoding='utf-8') as f:
			lines = f.readlines()
	except FileNotFoundError:
		print(f"Log file {log_path} not found.")
		return trades, total_return


	for line in lines:
		parts = line.strip().split(',')
		bot_name = parts[1]
		ticker = parts[2]
		action = parts[3]
		quantity = int(parts[4])
		price = float(parts[5])

		if f"[{bot_name}]" in line:
			# Line template: <timestamp>,<bot_name>,<ticker>,<action>,<amount>,<price>,<total>
			# Example line: "2026-01-12 18:44:01.019202,random_bot,MARA,BUY,157,10.6369,1669.9933"
			if len(parts) < 7:
				continue


			if action == "BUY":
				if ticker not in _positions:
					_positions[ticker] = []
				# Spara köpt kvantitet och pris
				_positions[ticker].append((quantity, price))
			elif action == "SELL":
				if ticker in _positions and _positions[ticker]:
					bought_quantity, bought_price = _positions[ticker].pop(0)
					if bought_quantity != quantity:
						print(
							f"Warning: Sold quantity {quantity} does not match bought quantity {bought_quantity} for {ticker}.")
					trade_return = (price - bought_price) * quantity
					total_return += trade_return
					trades.append(
						(ticker, bought_price, price, quantity, trade_return))

	return trades, total_return


if __name__ == "__main__":
	# List all bot names based on JSON files in the portfolios directory
	bot_names = [name for name in os.listdir(PATH_TILL_PORTFÖLJER) if os.path.isfile(
		os.path.join(PATH_TILL_PORTFÖLJER, name)) and name.endswith('.json')]
	for bot_name in bot_names:
		trades, total_return = find_trades_of_bot(
			bot_name.replace('.json', '.csv'), bot_name.replace('.json', ''))
		print(f"Bot: {bot_name.replace('.json', '')}")
		for trade in trades:
			ticker, buy_price, sell_price, quantity, trade_return = trade
			print(
				f"Ticker: {ticker}, Bought at: {buy_price}, Sold at: {sell_price}, Quantity: {quantity}, Return: {trade_return:.2f}")
		print(f"Total Return: {total_return:.2f}\n")
