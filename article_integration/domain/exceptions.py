class Exception(Exception):
    """Base class for exceptions in this module."""
    pass

class InvalidLink(Exception):
    """Exception raised for invalid links."""
    pass

class EmptyTitle(Exception):
    """Exception raised for empty titles."""
    pass

class FuturePublicationDate(Exception):
    """Exception raised for publication dates in the future."""
    pass

class EmptyContent(Exception):
    """Exception raised for empty content."""
    pass

class InvalidPublicationDate(Exception):
    """Exception raised for invalid publication dates."""
    pass

