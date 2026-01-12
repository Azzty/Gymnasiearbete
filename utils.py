"""
Kodfil med olika hjälpfunktioner och konstanter för att hålla ordning på saker
"""

from enum import Enum
import pandas
import os
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed


class ERROR_CODES(Enum):
    SUCCESS = 0
    INVALID_TICKER = 1
    INVALID_AMOUNT = 2
    PORTFOLIO_NOEXIST = 3
    BUYERROR = 4
    HISTORY_NOEXIST = 5
    INSUFFICIENT_AMOUNT = 6
    JSON_ERROR = 7
    NO_SHARES = 8
    ADD_SHARES_NOT_ALLOWED = 9
    PRICE_UNAVAILABLE = 10


# Determine the base directory of the project dynamically
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PATH_TILL_PRISER = os.path.join(BASE_DIR, "aktiepriser")
PATH_TILL_PORTFÖLJER = os.path.join(BASE_DIR, "portföljer")
PATH_TILL_LOGGAR = os.path.join(BASE_DIR, "portföljer", "loggar")


def _read_and_process_ticker(ticker: str, length: int):
    """Reads and processes the data for a single ticker from its CSV file.\n
    `length` is the amount of minutes from the end to read.
    Data is resampled to be in 1-minute intervals, where each datapoint is the last value during that time
    """
    price_path = os.path.join(PATH_TILL_PRISER, f"{ticker}.csv")
    if not os.path.isfile(price_path):
        print(f"Couldn't find file: {price_path}")
        return ticker, None

    try:
        # This logic efficiently reads the end of a potentially large CSV file
        # without loading the entire file into memory. It starts by reading a small
        # chunk from the end and doubles the chunk size until it has enough data
        # to cover the `long_period` for the EMA calculation.
        chunk_size = 1024 * 8  # Start with 8KB
        df = pandas.DataFrame()

        with open(price_path, 'rb') as f:
            # Get the total file size to read from the end
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            while True:
                # Calculate start position for reading, ensuring it's not negative
                read_pos = max(0, file_size - chunk_size)
                f.seek(read_pos)

                # Read and decode the chunk of the file
                tail_data = f.read().decode('utf-8')

                # If we didn't start at the beginning, the first line might be partial.
                # To avoid a parsing error, we find the first full newline and skip to it.
                if read_pos > 0:
                    first_newline = tail_data.find('\n')
                    if first_newline != -1:
                        tail_data = tail_data[first_newline + 1:]

                # Read the text chunk into a pandas DataFrame
                df = pandas.read_csv(StringIO(tail_data), names=[
                                     "TIME", "PRICE", "CHANGE_PERCENT", "CHANGE", "CUM_VOLUME"], header=None)

                # ta bort första rad om det är header
                if read_pos == 0:
                    if not df.empty and df.iloc[0]["TIME"] == "TIME":
                        df = df.iloc[1:]

                # Convert time strings to datetime objects. Invalid formats become NaT (Not a Time).
                df['TIME'] = pandas.to_datetime(
                    df['TIME'], format="%H:%M:%S", errors="coerce")
                df.dropna(subset=['TIME'], inplace=True)

                if df.empty:  # If chunk is empty or all times were invalid
                    if read_pos == 0:
                        break
                    chunk_size *= 2  # Not enough valid data, increase chunk size
                    continue

                # Check if the data we've read covers the required time window
                latest_time = df['TIME'].iloc[-1]
                earliest_needed = latest_time - \
                    pandas.Timedelta(minutes=length)
                earliest_in_df = df['TIME'].iloc[0]

                if earliest_in_df <= earliest_needed or read_pos == 0:
                    break  # We have enough data or have read the whole file

                chunk_size *= 2  # Not enough data, double the chunk size and retry

        # Ensure the 'PRICE' column is numeric, converting non-numeric values to NaN
        df['PRICE'] = pandas.to_numeric(df['PRICE'], errors='coerce')
        df['CUM_VOLUME'] = pandas.to_numeric(df['CUM_VOLUME'], errors='coerce')

        # Group by 1-minute intervals and calculate OHLCV
        ohlcv_df = df.groupby(pandas.Grouper(key='TIME', freq='1min')).agg(
            OPEN=('PRICE', 'first'),
            HIGH=('PRICE', 'max'),
            LOW=('PRICE', 'min'),
            PRICE=('PRICE', 'last'),  # 'PRICE' column becomes the 'Close'
            # Take the last cumulative volume for the minute
            CUM_VOLUME=('CUM_VOLUME', 'last')
        )

        # Get volume per trade instead of cumulative
        ohlcv_df['VOLUME'] = ohlcv_df['CUM_VOLUME'].diff().fillna(0)
        ohlcv_df.drop(columns=['CUM_VOLUME'], inplace=True)

        # Se till att alla kolumner finns även om ingen data finns för att förhindra KeyErrors
        if ohlcv_df.empty:
            df = pandas.DataFrame(
                columns=['OPEN', 'HIGH', 'LOW', 'PRICE', 'VOLUME'])
        else:
            df = ohlcv_df.ffill()

        return ticker, df

    except Exception as e:
        print(f"Error reading or processing {price_path}: {e}")
        return ticker, None


def retrieve_data(tickers: list[str], length: int):
    """Retrieves latest data from all stocks defined in tickers.
    This method uses a ThreadPoolExecutor to parallelize file reading.\n
    `length` is the amount of minutes from the end to read.\n
    returns a dictionary with dataframes containing all available data within the provided interval for each ticker.
    Data is resampled to be in 1-minute intervals, where each datapoint is the last value during that time"""
    dataframes = {}
    # Use a thread pool to read and process multiple CSV files concurrently.
    # This is highly effective for I/O-bound tasks like reading from disk.
    # `max_workers=None` lets the library choose an optimal number of threads.
    with ThreadPoolExecutor(max_workers=None) as executor:
        # Submit all file reading tasks to the pool.
        # `future_to_ticker` maps each running task (future) back to its stock ticker.
        future_to_ticker = {executor.submit(
            _read_and_process_ticker, t, length): t for t in tickers}

        # `as_completed` yields futures as they finish, allowing us to process results immediately.
        for future in as_completed(future_to_ticker):
            ticker, df = future.result()
            if df is not None and not df.empty:
                dataframes[ticker] = df

    return dataframes


if __name__ == "__main__":
    # testing
    print(ERROR_CODES(8).name)
