from matplotlib import pyplot as plt
import pandas_ta as ta
import numpy as np
import pandas
import os
from io import StringIO
from utils import PATH_TILL_PRISER


def find_intersects(s0: pandas.Series, s1: pandas.Series):
    """
    Finds intersects between two pandas series.
    returns a dict of time and type of intersection of all intersections.
    `s0` should be the shorter interval.
    """

    intersects = {}

    # p is for price
    prev_p0 = 0
    prev_p1 = 0

    for time in s1.to_dict().keys():
        p0 = s1[time]
        p1 = s0[time]
        if np.isnan(p0) or np.isnan(p1):
            continue
        if p0 > p1 and prev_p0 < prev_p1:
            intersects[time] = "under"
        elif p0 < p1 and prev_p0 > prev_p1:
            intersects[time] = "over"

        prev_p0 = p0
        prev_p1 = p1

    return intersects


PRISTABELL = "TESTTABELL3"
LONG = 21
SHORT = 9

df = pandas.DataFrame(
    columns=["TIME","PRICE","CHANGE_PERCENT","CHANGE"])

price_path = os.path.join(PATH_TILL_PRISER, f"{PRISTABELL}.csv")
if os.path.isfile(price_path):

    chunk_size = 1024 * 16  # Start with 16KB
    df = pandas.DataFrame()

    with open(price_path, 'rb') as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()

        while True:
            read_pos = max(0, file_size - chunk_size)
            f.seek(read_pos)

            # Read and decode the chunk
            tail_data = f.read().decode('utf-8')

            # If we didn't start at the beginning, the first line might be partial, so we skip it.
            if read_pos > 0:
                first_newline = tail_data.find('\n')
                if first_newline != -1:
                    tail_data = tail_data[first_newline + 1:]

            # Create a DataFrame from the chunk
            df = pandas.read_csv(StringIO(tail_data), names=[
                "TIME", "PRICE", "CHANGE_PERCENT", "CHANGE"], header=None if read_pos > 0 else 0)

            # Check if we have enough data
            df['TIME'] = pandas.to_datetime(
                df['TIME'], format="%H:%M:%S", errors="coerce").dt.time
            df.dropna(subset=['TIME'], inplace=True)

            if df.empty:  # If chunk is empty or all times are invalid
                if read_pos == 0:
                    break  # Reached start of file
                chunk_size *= 2  # Read more data
                continue

            latest_time = pandas.Timestamp.combine(
                pandas.Timestamp.today().date(), df['TIME'].iloc[-1])
            earliest_needed = latest_time - \
                pandas.Timedelta(minutes=LONG)
            earliest_in_df = pandas.Timestamp.combine(
                pandas.Timestamp.today().date(), df['TIME'].iloc[0])

            if earliest_in_df <= earliest_needed or read_pos == 0:
                break  # We have enough data or have read the whole file

            chunk_size *= 2  # Not enough data, double the chunk size and retry

# Se till att alla tider är idag
today = pandas.Timestamp.now().date()
df['TIME'] = df['TIME'].apply(lambda t: pandas.Timestamp.combine(today, t))

# Konvertera priser till siffor
df['PRICE'] = pandas.to_numeric(df['PRICE'], errors='coerce')

# Se till att datan är i 1 minuts intervall
df = df.resample("1min", on='TIME').mean()

ema_short = ta.ema(df['PRICE'], SHORT)
ema_long = ta.ema(df['PRICE'], LONG)

intersects = find_intersects(ema_short, ema_long)
print(intersects)
plt.plot(df['PRICE'], label="price")
plt.plot(ema_short, label="short")
plt.plot(ema_long, label="long")
plt.legend()
plt.show()
