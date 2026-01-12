from matplotlib import pyplot
import yfinance as yf

portfolio = {
	"aktier": {
        "DNN": 8456,
        "BABA": 123,
        "AMZN": 84,
        "NVO": 405,
        "KSS": 1422,
        "ET": 1063,
        "IONQ": 734,
        "HBAN": 1525,
        "PFE": 1145,
        "CLSK": 1353,
        "ONDS": 1748,
        "NFLX": 139,
        "GRAB": 2731,
        "F": 2631,
        "SMR": 721,
        "SMCI": 408,
        "BE": 142,
        "NOK": 2038,
        "BAC": 230,
        "LEN": 94,
        "CIFR": 751,
        "NBIS": 140,
        "AGNC": 1133,
        "SOUN": 972,
        "CRCL": 163,
        "QUBT": 1807,
        "ACHR": 1488,
        "BBAI": 3423,
        "NVDA": 116,
        "BTE": 8576,
        "RIVN": 625,
        "PSNYW": 37844,
        "CCL": 339,
        "ITUB": 1180
    }
}

for t in portfolio['aktier'].keys():
    pyplot.plot(yf.Ticker(t).history(period="2mo", interval="1d")['Close'], label=t)

pyplot.legend()
pyplot.show()