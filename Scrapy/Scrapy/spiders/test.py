import scrapy

class MySpider(scrapy.Spider):
    name = "myspider"
    start_urls = ["https://www.investing.com/equities/most-active-stocks"]
    handle_httpstatus_list = [403]   # fånga 403 så vi kan läsa body
    
    def parse(self, response):
        self.logger.info("STATUS: %s", response.status)
        open("debug_response.html", "wb").write(response.body[:10000])  # spara första delen
        self.logger.info("Saved debug_response.html")
        # inspectera filen i en webbläsare
