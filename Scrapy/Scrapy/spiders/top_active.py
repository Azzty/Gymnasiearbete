import scrapy

class MostActiveSpider(scrapy.Spider):
  name = 'most_active_spider'
  
  # Hämta json data med 100 mest aktiva aktier direkt från yahoos servrar
  start_urls = [
    "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?scrIds=most_actives&count=100"
  ]
  
  # Extrahera tickers
  def parse(self, response):
    data = response.json()
    for item in data["finance"]["result"][0]["quotes"]:
      yield {
        "ticker": item["symbol"]
      }