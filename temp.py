import yfinance as yf
from utils import PATH_TILL_PRISER
import os
import csv
import datetime as dt
import pandas

t = 'AAPL'

data = yf.download(t, period="1d", interval="1m")
print(data)

with open(os.path.join(PATH_TILL_PRISER, t + ".csv"), "a", encoding="utf-8", newline="") as f:
    writer = csv.writer(f, delimiter=",", quotechar='"',
                        quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["TIME", "PRICE", "CHANGE_PERCENT", "CHANGE", "CUM_VOLUME"])
    cum_volume = 0
    for index, row in data.iterrows():
      cum_volume += row.values[-1]
      data_to_write = [dt.datetime.strftime(pandas.to_datetime(index), "%H:%M:%S")]
      data_to_write.extend([list(row.values)[1], 0.0, 0.0, cum_volume])
      writer.writerow(data_to_write)
