import websocket
import _thread
import time
import rel
import json


def on_message(ws, message):
    print("Recieved message:")
    print(message)


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws: websocket.WebSocketApp):
    print("Opened connection")
    ws.send(json.dumps({"subscribe": ["AAPL", "MSFT", "NVDA"]}))


if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("wss://streamer.finance.yahoo.com",
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)

    # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    ws.run_forever(dispatcher=rel, reconnect=5)
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
