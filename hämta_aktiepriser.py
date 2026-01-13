import yfinance as yf
import os
import csv
import datetime as dt
from collections import deque
import logging
from threading import Thread, Lock, Event
import threading
from utils import PATH_TILL_PRISER, thread_safe_print
import operator
import time
from websockets import exceptions as ws_exceptions

"""Tack Gemini för att du optimiserade min fil :D"""

# Stäng av DEBUG-loggning från yfinance och dess beroenden
logging.getLogger('yfinance').setLevel(logging.CRITICAL)
logging.getLogger('yfrlt').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.CRITICAL)
logging.getLogger('peewee').setLevel(logging.WARNING)

DATA_QUEUE = deque()
QUEUE_LOCK = Lock()
STOP_EVENT = Event()

# Aktiepriser ska rensas varje dag eftersom vi bara använder dagens prisdata.
# Dessa filer i mappen Gymnasiearbete/aktiepriser ska bevaras mellan varje session, dvs inte tas bort.
FILES_TO_KEEP = ['_date.txt', 'TESTTABELL.csv',
                 'TESTTABELL2.csv', 'TESTTABELL3.csv']

MAX_WEBSOCKET_SESSION_TIME = 10 * 60  # 10 minuter (yfinance har en tendens att koppla bort efter en stund)

last_ticker_update = 0.0
_tickers_to_monitor = []

def message_handler(message):
    global last_ticker_update
    """Handles incoming messages from the WebSocket and adds them to a thread-safe queue."""
    # market_hours 1 means normal market hours, which is what we want. Discard anything else.
    if message.get("market_hours") != 1:
        thread_safe_print("datapoint not in regular market:", message)
        return

    last_ticker_update = time.time()
    with QUEUE_LOCK:
        DATA_QUEUE.append(message)


def data_writer():
    """
    Worker thread function.
    Periodically processes messages from the queue and writes them to ticker-specific CSV files.
    """
    thread_safe_print("Data writer thread started.")
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
                thread_safe_print(time.strftime("%H:%M:%S"),"Antal prisändringar:", sum(price_updates.values()), flush=True)
                top_stocks = dict(sorted(price_updates.items(), key=operator.itemgetter(1), reverse=True)[:5])
                thread_safe_print("Mest ändringar: ", top_stocks)
                update_timer = 0
                price_updates.clear()
    finally:
        # Ensure all files are closed on exit
        for f, _ in open_files.values():
            f.close()
        thread_safe_print("Data writer thread stopped and files closed.")


# Globala variabler för att hantera WebSocket och trådar
_ws = None
_writer_thread = None
_listener_thread = None
is_restarting_websocket = False

def start_websocket_watchdog(timeout: int = 5):
    """Kontrollerar WebSocket-anslutningen och återansluter vid behov.
    Körs i en separat tråd.
    Behöver startas manuellt efter att monitor_stocks har anropats.
    """
    global last_ticker_update, _tickers_to_monitor, is_restarting_websocket
    last_ticker_update = time.time()
    session_start = time.time()
    while not STOP_EVENT.is_set():
        time.sleep(timeout)  # Kontrollera var (timeout) sekunder
        if is_restarting_websocket:
            continue  # Hoppa över kontrollen om vi redan håller på att återansluta
        if time.time() - last_ticker_update >= timeout:
            thread_safe_print("-------------------------------\n"
            "WebSocket watchdog: No messages received in the last "
                  f"{timeout} seconds. Reconnecting...\n"
                  "-------------------------------", flush=True)
            is_restarting_websocket = True
            stop_monitoring()
            _listener_thread.join(timeout=5)  # Vänta på att lyssnartråden ska avslutas
            monitor_stocks(_tickers_to_monitor)
            is_restarting_websocket = False
            session_start = time.time()  # Återställ sessionens starttid
        elif time.time() - session_start >= MAX_WEBSOCKET_SESSION_TIME:
            thread_safe_print("-------------------------------\n"
                  "WebSocket watchdog: Maximum session time reached. Reconnecting...\n" \
                  "-------------------------------", flush=True)
            is_restarting_websocket = True
            stop_monitoring()
            _listener_thread.join(timeout=5)  # Vänta på att lyssnartråden ska avslutas
            monitor_stocks(_tickers_to_monitor)
            is_restarting_websocket = False
            session_start = time.time()  # Återställ sessionens starttid

def _start_listening(tickers_to_monitor):
    """Intern funktion som körs i en egen tråd för att lyssna på WebSocket."""
    global _ws, _tickers_to_monitor
    while not STOP_EVENT.is_set():
        try:
            with yf.WebSocket() as ws:
                _ws = ws
                _tickers_to_monitor = tickers_to_monitor
                ws.subscribe(tickers_to_monitor)
                ws.listen(message_handler)
        except ws_exceptions.ConnectionClosedOK:
            # Normal/expected close (e.g. due to calling stop_monitoring()). Don't print exception text.
            logging.info("WebSocket closed normally; reconnecting in 1s.")
            time.sleep(1)  # Vänta lite innan återanslutning
        except ws_exceptions.ConnectionClosedError as e:
            # Non-OK close codes — warn and reconnect
            logging.warning("WebSocket closed with error (%s); reconnecting in 5s.", e)
            time.sleep(5)
        except Exception:
            # Unexpected errors: include stacktrace for debugging
            logging.exception("Unexpected WebSocket error; reconnecting in 5s.")
            time.sleep(5)  # Vänta lite längre vid fel innan återanslutning
        finally:
            thread_safe_print("WebSocket listener has stopped.")


def monitor_stocks(tickers_to_monitor: list[str]):
    """Creates a websocket using yfinance to listen to all tickers in tickers_to_monitor"""
    global _writer_thread, _listener_thread, last_ticker_update

    STOP_EVENT.clear()
    
    if not tickers_to_monitor:
        raise ValueError(
            "No tickers were supplied to monitor_stocks. The list cannot be empty.")
    
    # Ta bort gammal aktiedata
    today_date = str(dt.date.today())
    with open(os.path.join(PATH_TILL_PRISER, "_date.txt"), "r+") as f:
        if f.read() != today_date:
            thread_safe_print("\n--------- NY DAG! TAR BORT GAMLA FILER ---------")
            remove_count = 0
            for filename in os.listdir(PATH_TILL_PRISER):
                if filename in FILES_TO_KEEP:
                    continue
                else:
                    filepath = os.path.join(PATH_TILL_PRISER, filename)
                    if os.path.isfile(filepath):
                        os.remove(filepath)
                        remove_count += 1
            thread_safe_print(f"Tog bort {remove_count} filer\n")
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
    thread_safe_print("Shutting down monitoring...")
    if _ws:
        _ws.close()
    STOP_EVENT.set()
    if _writer_thread and _writer_thread != threading.current_thread():
        _writer_thread.join(timeout=5)  # Vänta på att skrivartråden ska avslutas, med en timeout
        if _writer_thread.is_alive():
            thread_safe_print("Warning: Data writer thread did not shut down gracefully.")
        if _listener_thread and _listener_thread != threading.current_thread():
            _listener_thread.join(timeout=5)  # Vänta på att lyssnartråden ska avslutas, med en timeout
            if _listener_thread.is_alive():
                thread_safe_print("Warning: WebSocket listener thread did not shut down gracefully.")
    thread_safe_print("Monitoring shutdown complete.")
