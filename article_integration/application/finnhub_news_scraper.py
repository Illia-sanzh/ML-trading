import datetime
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from article_integration.domain.news_article import NewsArticle
from article_integration.domain.exceptions import FinnhubNewsScraperError



class FinnhubNewsScraper:
    def __init__(self, api_key: str):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY", api_key)
        if not self.api_key:
            raise ValueError("Finnhub API key must be provided either as an argument or in the environment variable 'FINNHUB_API_KEY'.")
        self.base_url = "https://finnhub.io/api/v1/news"


    def fetch_news(self, from_date: datetime.date, to_date: datetime.date, symbol: str) -> list[NewsArticle]:
        if not isinstance(from_date, datetime.date) or not isinstance(to_date, datetime.date):
            raise ValueError("from_date and to_date must be datetime.date objects.")
        params = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "symbol": symbol.upper(),
            "token": self.api_key
        }
        if not symbol.strip():
            raise ValueError("Symbol must be a non-empty string.")
        if from_date > to_date:
            raise ValueError("From date cannot be later than to date.")
        if not from_date:
            raise ValueError("From date must be provided.")
        if not to_date:
            raise ValueError("To date must be provided.")

        request = Request(f"{self.base_url}?{urlencode(params)}")
        headers = {"Accept": "application/json"}

        try:
            with urlopen(request) as response:
                data = json.loads(response.read().decode())
                return [self._map_to_news_article(item) for item in data]
        except Exception as e:
            raise FinnhubNewsScraperError(f"Failed to fetch news from Finnhub: {e}")

        if not isinstance(data, list):
            raise FinnhubNewsScraperError("Invalid data format received from Finnhub. Expected a list of news items.")
        
        return [self._map_to_news_article(item) for item in data]

    def _map_to_news_article(self, item: dict) -> NewsArticle:

        if not isinstance(item, dict):
            raise FinnhubNewsScraperError("Invalid data format received from Finnhub. Expected a dictionary.")

        required_keys = {"id", "headline", "summary", "datetime", "url"}
        if not required_keys.issubset(item.keys()):
            raise FinnhubNewsScraperError(f"Missing required keys in Finnhub news item. Required keys: {required_keys}, received keys: {item.keys()}")

        timestamp = item.get("datetime")
        if not isinstance(timestamp, (int, float)):
            raise FinnhubNewsScraperError(f"Invalid datetime format in Finnhub news item. Expected a timestamp (int or float), received: {timestamp}")

        try:
            article_id = item.get("id")
            title = item.get("headline")
            content = item.get("summary")
            publication_date = datetime.datetime.fromtimestamp(item.get("datetime"))
            link = item.get("url")

            return NewsArticle(
                article_id=article_id,
                title=title,
                content=content,
                publication_date=publication_date,
                link=link
            )
        except Exception as e:
            raise FinnhubNewsScraperError(f"Failed to map Finnhub news item to NewsArticle: {e}")

