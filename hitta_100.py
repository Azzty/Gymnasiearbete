"""
1. Hitta de 100 mest aktiva aktierna
2. Ladda ner senaste månadens data för alla aktier
3. Låt varje bot behandla datan och göra 
"""

import yfinance as yf
import json
import subprocess
import sys
import os
from Scrapy.Scrapy.spiders.top_active import MostActiveSpider

# Hitta den absoluta sökvägen till Scrapy-projektet
SCRAPY_PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'Scrapy', 'Scrapy'))

def get_most_active_stocks():
    """Fetches the 100 most active stocks from yahoo finance.\n
    Returns a string of all tickers separated by a space (as used in `yfinance.download()`)"""

    # Skapa en temporär fil för att spara resultatet från Scrapy
    output_file = os.path.join(SCRAPY_PROJECT_PATH, '..', 'temp_active_stocks.json')

    # Använd subprocess för att köra Scrapy i en separat process.
    # Detta kringgår "ReactorNotRestartable" felet när funktionen anropas flera gånger.
    command = [
        sys.executable,  # Sökvägen till python.exe
        "-m", "scrapy",
        "runspider",
        os.path.join(SCRAPY_PROJECT_PATH, "spiders", "top_active.py"),
        "-o", output_file,
        "--nolog" # Minska mängden output i konsolen
    ]

    # Kör kommandot och vänta tills det är klart
    subprocess.run(command, check=True, cwd=os.path.dirname(SCRAPY_PROJECT_PATH))

    # Läs resultatet från den temporära filen
    try:
        with open(output_file, 'r') as f:
            items = json.load(f)
        # Extrahera tickers och sätt ihop dem till en sträng
        tickers = " ".join([item["ticker"] for item in items])
        return tickers
    finally:
        # Städa upp och ta bort filen
        if os.path.exists(output_file):
            os.remove(output_file)


if __name__ == "__main__":
    tickers = get_most_active_stocks()
    # Plotta aktiepriserna på en graf
    from matplotlib import pyplot
    df = yf.download(tickers, period="1d", interval="1m")
    print(df)
    pyplot.plot(df['Close'])
    pyplot.show()
