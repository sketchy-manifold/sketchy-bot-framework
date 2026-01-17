"""Dummy API configuration for use in development and tests."""

class APIConfig:
    # Replace these values with real credentials in api_config.py (ignored in git)
    API_KEY = "dummy-api-key"
    USER_ID = "dummy_user_id"
    USERNAME = "dummy_username"
    # Number of seconds to cache GET responses by default
    CACHE_TTL = 60

    # Per-endpoint cache TTL overrides. Keys should match the relative API
    # endpoint paths used in ``ManifoldClient._make_request``.
    ENDPOINT_CACHE_TTLS = {
        'get-user-portfolio': 60 * 60 * 6,
        'get-user-portfolio-history': 60 * 60 * 6,
    }
