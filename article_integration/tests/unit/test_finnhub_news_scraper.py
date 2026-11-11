import datetime
import json
import os
from dotenv import load_dotenv
load_dotenv()  
import pytest

from article_integration.application.finnhub_news_scraper import FinnhubNewsScraper
from article_integration.domain.exceptions import FinnhubNewsScraperError
api_key = os.getenv("FINNHUB_API_KEY")  

def valid_news_article_data():
    return {
        "id": "67",
        "headline": "Sample News Article",
        "content": "This is a sample news article summary.",
        "datetime": int(datetime.datetime.now().timestamp()),
        "url": "https://example.com/sample-news-article"
    }

@pytest.mark.parametrize("invalid_data", [
    None,
    [],
    {},
    {"id": "67", "headline": "Sample News Article"},
    {"id": "67", "headline": "Sample News Article", "content": "This is a sample news article summary."},
    {"id": "67", "headline": "Sample News Article", "content": "This is a sample news article summary.", "datetime": int(datetime.datetime.now().timestamp()), "url": "https://example.com/sample-news-article"},
])
def test_map_to_news_article_invalid_data(invalid_data):
    scraper = FinnhubNewsScraper(api_key="dummy_api_key")
    with pytest.raises(FinnhubNewsScraperError):
        scraper._map_to_news_article(invalid_data)


@pytest.mark.parametrize("invalid_timestamp", [
    "invalid-timestamp",
    None,
    {},
    [],
    123.456,  
])
def test_map_to_news_article_invalid_timestamp(invalid_timestamp):
    scraper = FinnhubNewsScraper(api_key="dummy_api_key")
    valid_data = valid_news_article_data()
    valid_data["datetime"] = invalid_timestamp

    with pytest.raises(FinnhubNewsScraperError):
        scraper._map_to_news_article(valid_data)

@pytest.mark.parametrize("invalid_symbol", [
    "",
    "   ",
    "\n",
    "\t",
])
def test_fetch_news_invalid_symbol(invalid_symbol):
    scraper = FinnhubNewsScraper(api_key="dummy_api_key")
    from_date = datetime.date(2023, 1, 1)
    to_date = datetime.date(2023, 1, 31)

    with pytest.raises(ValueError):
        scraper.fetch_news(from_date, to_date, invalid_symbol)

@pytest.mark.parametrize("from_date, to_date", [
    (datetime.date(2023, 2, 1), datetime.date(2023, 1, 31)), 
    (None, datetime.date(2023, 1, 31)), 
    (datetime.date(2023, 1, 1), None),  
])
def test_fetch_news_invalid_date_range(from_date, to_date):
    scraper = FinnhubNewsScraper(api_key="dummy_api_key")
    symbol = "AAPL"

    with pytest.raises(ValueError):
        scraper.fetch_news(from_date, to_date, symbol)



def test_valid_request_and_mapping():
    scraper = FinnhubNewsScraper(api_key=api_key)
    from_date = datetime.date(2023, 1, 1)
    to_date = datetime.date(2023, 1, 31)
    symbol = "AAPL"

    try:
        news_articles = scraper.fetch_news(from_date, to_date, symbol)
        assert isinstance(news_articles, list)
        for article in news_articles:
            assert hasattr(article, "article_id")
            assert hasattr(article, "title")
            assert hasattr(article, "content")
            assert hasattr(article, "publication_date")
            assert hasattr(article, "link")
    except FinnhubNewsScraperError as e:
        pytest.fail(f"FinnhubNewsScraperError raised unexpectedly: {e}")