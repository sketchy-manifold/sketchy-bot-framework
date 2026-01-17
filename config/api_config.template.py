"""Template for API configuration. Copy to api_config.py and fill in your values."""

class APIConfig:
    # Get your API key from https://manifold.markets/profile
    API_KEY = "your-api-key-here"

    USER_ID = 'asdfuseridasdf'
    USERNAME = 'MyUserName'
    # Number of seconds to cache GET responses by default
    CACHE_TTL = 3  # Should generally be quite short

    # Per-endpoint cache TTL overrides. Keys should match the relative API
    # endpoint paths used in ``ManifoldClient._make_request``.
    ENDPOINT_CACHE_TTLS = {
        'get-user-portfolio': 60 * 60 * 6,
        'get-user-portfolio-history': 60 * 60 * 6,
    }


