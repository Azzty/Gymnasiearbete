import json
import os
from utils import PATH_TILL_PORTFÖLJER
import handla_aktie as ha
import sys
import threading

# Check specific bot
bot_name = 'tmf_bot'  # Change this to the bot you want to check
path = os.path.join(PATH_TILL_PORTFÖLJER, bot_name + '.json')
with open(path, 'r') as f:
    portfolio = json.load(f)
    f.close()
value = portfolio['fria_pengar']
for t, amt in portfolio['aktier'].items():
    price, _ = ha._get_stock_price(t)
    if price is not None:
        value += price * amt
    else:
        print(f'No price for {t}')
print(f'{bot_name}: {value:.2f}')