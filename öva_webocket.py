import yfrlt
import threading
import time

## Monitoring med yfrlt (vet )

def on_price_update(data):
    print(f"{data.symbol}: {data.price:.4f} ({data.change_percent:+.2f}%)")
    print(f"Market hours: {data.market_hours}, Exchange: {data.exchange}")

# Create client
client = yfrlt.Client()
client.subscribe(["TTE.PA"], on_price_update)

# Run client in a separate thread
def run_client():
    client.start()  # blocks and streams indefinitely

thread = threading.Thread(target=run_client)
thread.start()

# Main thread can now do other things, or just sleep
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping stream...")
    client.stop()  # gracefully stop
    thread.join()
