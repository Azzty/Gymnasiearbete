import json
import os
from utils import PATH_TILL_PORTFÖLJER
import handla_aktie as ha

bots = ['obv_bot', 'rsi_bot', 'macd_crossover_bot', 'ema_crossover_bot']

for bot in bots:
    path = os.path.join(PATH_TILL_PORTFÖLJER, bot + '.json')
    with open(path, 'r') as f:
        portfolio = json.load(f)
    contributions = []
    for t, amt in portfolio['aktier'].items():
        price, _ = ha._get_stock_price(t)
        if price is not None:
            value = price * amt
            contributions.append((t, amt, price, value))
    contributions.sort(key=lambda x: x[3], reverse=True)
    print(f'\n{bot}:')
    total_value = sum(c[3] for c in contributions) + portfolio['fria_pengar']
    print(f'Total value: {total_value:.2f}')
    for t, amt, price, value in contributions[:5]:  # top 5
        pct = (value / total_value) * 100
        print(f'  {t}: {amt} shares @ {price:.2f} = {value:.2f} ({pct:.1f}%)')