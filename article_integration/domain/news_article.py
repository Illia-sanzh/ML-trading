import datetime
from article_integration.domain.exceptions import InvalidLink, EmptyTitle, FuturePublicationDate, EmptyContent, InvalidPublicationDate
class NewsArticle:
    def __init__(self, article_id, title, content, publication_date, link):
        self.article_id = article_id
        self.title = title
        self.content = content
        self.publication_date = publication_date
        self.link = link

        self.validate()

    def validate(self):
        if not self.title:
            raise EmptyTitle("Title cannot be empty.")
        if not self.content:
            raise EmptyContent("Content cannot be empty.")
        if not isinstance(self.publication_date, datetime.datetime):
            raise InvalidPublicationDate("Publication date must be a datetime object.")
        if self.publication_date > datetime.datetime.now():
            raise FuturePublicationDate("Publication date cannot be in the future.")
        if not self.link.startswith("http"):
            raise InvalidLink("Link must be a valid URL starting with 'http'.")