import yfinance as yf
import pandas_ta as ta
import matplotlib.pyplot as plt

dataframe = yf.download('aapl')

plt.plot(dataframe["Close"])

print(type(dataframe["Close"]["AAPL"]))
sma = ta.sma(dataframe["Close"]["AAPL"], length=14)
plt.plot(dataframe.index, sma)
ema = ta.ema(dataframe["Close"]["AAPL"], length=14)
plt.plot(dataframe.index, ema)
plt.legend()
plt.figure(2)
rsi = ta.rsi(dataframe["Close"]["AAPL"], length=9)
plt.plot(dataframe.index, rsi)
plt.show()