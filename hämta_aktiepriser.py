import yfinance as yf
import os
import csv
import datetime as dt
from collections import deque
import logging
from threading import Thread, Lock, Event
import threading
from utils import PATH_TILL_PRISER
import operator
import time

"""Tack Gemini för att du optimiserade min fil :D"""

# Stäng av DEBUG-loggning från yfinance och dess beroenden
logging.getLogger('yfinance').setLevel(logging.WARNING)
logging.getLogger('yfrlt').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('peewee').setLevel(logging.WARNING)

DATA_QUEUE = deque()
QUEUE_LOCK = Lock()
STOP_EVENT = Event()

# Aktiepriser ska rensas varje dag eftersom vi bara använder dagens prisdata.
# Dessa filer i mappen Gymnasiearbete/aktiepriser ska bevaras mellan varje session, dvs inte tas bort.
FILES_TO_KEEP = ['_date.txt', 'TESTTABELL.csv',
                 'TESTTABELL2.csv', 'TESTTABELL3.csv']

last_ticker_update = 0.0
_tickers_to_monitor = []

def message_handler(message):
    global last_ticker_update
    """Handles incoming messages from the WebSocket and adds them to a thread-safe queue."""
    # market_hours 1 means normal market hours, which is what we want. Discard anything else.
    if message.get("market_hours") != 1:
        print("datapoint not in regular market:", message)
        return

    last_ticker_update = time.time()
    with QUEUE_LOCK:
        DATA_QUEUE.append(message)


def data_writer():
    """
    Worker thread function.
    Periodically processes messages from the queue and writes them to ticker-specific CSV files.
    """
    print("Data writer thread started.")
    open_files = {}  # Cache for open file writers
    price_updates = {}  # Håll koll på alla prisuppdateringar så man får lite live-feedback
    update_timer = 0
    try:
        while not STOP_EVENT.is_set() or DATA_QUEUE:
            messages_to_write = []
            with QUEUE_LOCK:
                while DATA_QUEUE:
                    messages_to_write.append(DATA_QUEUE.popleft())

            if messages_to_write:
                for msg in messages_to_write:
                    ticker = msg['id']

                    if ticker not in price_updates:
                        price_updates[ticker] = 0
                    price_updates[ticker] += 1

                    if ticker not in open_files:
                        filepath = os.path.join(
                            PATH_TILL_PRISER, f"{ticker}.csv")
                        # Open in append mode, create if it doesn't exist
                        f = open(filepath, "a", encoding="utf-8", newline="")
                        writer = csv.writer(f)
                        # Write header if the file is new/empty
                        if os.path.getsize(filepath) == 0:
                            writer.writerow(
                                ["TIME", "PRICE", "CHANGE_PERCENT", "CHANGE", "CUM_VOLUME"])
                        open_files[ticker] = (f, writer)

                    _, writer = open_files[ticker]
                    # yfinance timestamp is in milliseconds
                    trade_time = dt.datetime.fromtimestamp(
                        float(msg["time"]) / 1000).time()
                    writer.writerow([trade_time.strftime("%H:%M:%S"), msg.get("price"), msg.get(
                        "change_percent"), msg.get("change"), msg.get("day_volume")])

            # Write to the file from the buffer
            for tuple in open_files.values():
                tuple[0].flush()

            # Wait before checking the queue again to avoid busy-waiting
            STOP_EVENT.wait(timeout=1.0)
            update_timer += 1
            if update_timer >= 10:
                print("Antal prisändringar:", sum(price_updates.values()))
                top_stocks = dict(sorted(price_updates.items(), key=operator.itemgetter(1), reverse=True)[:5])
                print("Mest ändringar: ", top_stocks)
                update_timer = 0
                price_updates.clear()

            if time.time() - last_ticker_update >= 5:
                print("WARNING: More than 5 seconds has elapsed since last websocket message. Trying to reconnect...")
                stop_monitoring()
                monitor_stocks(_tickers_to_monitor)
                return
    finally:
        # Ensure all files are closed on exit
        for f, _ in open_files.values():
            f.close()
        print("Data writer thread stopped and files closed.")


# Globala variabler för att hantera WebSocket och trådar
_ws = None
_writer_thread = None
_listener_thread = None

def _start_listening(tickers_to_monitor):
    """Intern funktion som körs i en egen tråd för att lyssna på WebSocket."""
    global _ws, _tickers_to_monitor
    with yf.WebSocket() as ws:
        _ws = ws
        _tickers_to_monitor = tickers_to_monitor
        # print(f"Subscribing to: {', '.join(tickers_to_monitor)}")
        ws.subscribe(tickers_to_monitor)
        print(f"Listening for trades on: {', '.join(tickers_to_monitor)}")
        ws.listen(message_handler)
    print("WebSocket listener has stopped.")


def monitor_stocks(tickers_to_monitor: list[str]):
    """Creates a websocket using yfinance to listen to all tickers in tickers_to_monitor"""
    global _writer_thread, _listener_thread, last_ticker_update
    STOP_EVENT.clear()
    last_ticker_update = time.time()
    if not tickers_to_monitor:
        raise ValueError(
            "No tickers were supplied to monitor_stocks. The list cannot be empty.")

    # Ta bort gammal aktiedata
    today_date = str(dt.date.today())
    with open(os.path.join(PATH_TILL_PRISER, "_date.txt"), "r+") as f:
        if f.read() != today_date:
            print("\n--------- NY DAG! TAR BORT GAMLA FILER ---------")
            remove_count = 0
            for filename in os.listdir(PATH_TILL_PRISER):
                if filename in FILES_TO_KEEP:
                    continue
                else:
                    filepath = os.path.join(PATH_TILL_PRISER, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        remove_count += 1
            print(f"Tog bort {remove_count} filer\n")
            f.truncate(0)
            f.seek(0)
            f.write(today_date)

    # Starta dataskrivartråden
    _writer_thread = Thread(target=data_writer, daemon=True)
    _writer_thread.start()

    # Starta lyssnartråden
    _listener_thread = Thread(target=_start_listening, args=(tickers_to_monitor,), daemon=True)
    _listener_thread.start()


def stop_monitoring():
    """Stänger WebSocket-anslutningen och stoppar bakgrundstrådarna."""
    print("Shutting down monitoring...")
    if _ws:
        _ws.close()
    STOP_EVENT.set()
    if _writer_thread and _writer_thread != threading.current_thread():
        _writer_thread.join(timeout=5)  # Vänta på att skrivartråden ska avslutas, med en timeout
        if _writer_thread.is_alive():
            print("Warning: Data writer thread did not shut down gracefully.")
    print("Shutdown complete.")
