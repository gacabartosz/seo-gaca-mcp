"""Generic HTTP client for making requests within the seoleo API layer."""

from datetime import datetime, timezone


class HttpClient:
    """Minimal HTTP client stub for seoleo API integrations."""

    def __init__(self, base_url: str = "", timeout: int = 30, headers: dict = None):
        """Initialize the client with a base URL and optional default headers."""
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}

    def get(self, path: str, params: dict = None) -> dict:
        """Perform a GET request. Not yet implemented."""
        return {
            "status": "not_implemented",
            "message": "HttpClient.get() is not yet implemented.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def post(self, path: str, payload: dict = None) -> dict:
        """Perform a POST request. Not yet implemented."""
        return {
            "status": "not_implemented",
            "message": "HttpClient.post() is not yet implemented.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
