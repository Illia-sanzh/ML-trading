import pytest
import datetime, uuid
import sys
sys.path.append("article_integration/domain")
from article_integration.domain.news_article import NewsArticle
from article_integration.domain.exceptions import InvalidLink, EmptyTitle, FuturePublicationDate, EmptyContent, InvalidPublicationDate


def test_news_article_validity():
    article = NewsArticle(
        article_id=uuid.uuid4(),
        title="Sample News Article",
        content="This is a sample news article content.",
        publication_date=datetime.datetime.now(),
        link="https://example.com/sample-news-article"
    )

    assert article.article_id == article.article_id
    assert article.title == "Sample News Article"
    assert article.content == "This is a sample news article content."
    assert isinstance(article.publication_date, datetime.datetime)
    assert article.link == "https://example.com/sample-news-article"

def test_news_article_invalid_link():
    with pytest.raises(InvalidLink):
        NewsArticle(
            article_id=uuid.uuid4(),
            title="Invalid Link Article",
            content="This article has an invalid link.",
            publication_date=datetime.datetime.now(),
            link="invalid-link"
        )

    assert True 

def test_news_article_empty_title():
    with pytest.raises(EmptyTitle):
        NewsArticle(
            article_id=uuid.uuid4(),
            title="",
            content="This article has an empty title.",
            publication_date=datetime.datetime.now(),
            link="https://example.com/empty-title-article"
        )

    assert True

def test_news_article_future_publication_date():
    future_date = datetime.datetime.now() + datetime.timedelta(days=1)
    with pytest.raises(FuturePublicationDate):
        NewsArticle(
            article_id=uuid.uuid4(),
            title="Future Publication Date Article",
            content="This article has a future publication date.",
            publication_date=future_date,
            link="https://example.com/future-publication-date-article"
        )

    assert True

def test_news_article_empty_content():
    with pytest.raises(EmptyContent):
        NewsArticle(
            article_id=uuid.uuid4(),
            title="Empty Content Article",
            content="",
            publication_date=datetime.datetime.now(),
            link="https://example.com/empty-content-article"
        )

    assert True

def test_news_article_invalid_publication_date_type():
    with pytest.raises(InvalidPublicationDate):
        NewsArticle(
            article_id=uuid.uuid4(),
            title="Invalid Publication Date Type Article",
            content="This article has an invalid publication date type.",
            publication_date="2023-01-01", 
            link="https://example.com/invalid-publication-date-type-article"
        )

    assert True

@pytest.mark.parametrize(
    "title, content, publication_date, link, expected_exception",
    [
        ("", "Content", datetime.datetime.now(), "https://example.com", EmptyTitle),
        ("Title", "", datetime.datetime.now(), "https://example.com", EmptyContent),
        ("Title", "Content", datetime.datetime.now() + datetime.timedelta(days=1), "https://example.com", FuturePublicationDate),
        ("Title", "Content", "2023-01-01", "https://example.com", InvalidPublicationDate), 
        ("Title", "Content", datetime.datetime.now(), "invalid-link", InvalidLink),
    ]
)
def test_news_article_validation(title, content, publication_date, link, expected_exception):
    with pytest.raises(expected_exception):
        NewsArticle(
            article_id=uuid.uuid4(),
            title=title,
            content=content,
            publication_date=publication_date,
            link=link
        )

