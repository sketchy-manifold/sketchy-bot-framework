import requests
from typing import Optional, Tuple, Dict, Any

API_BASE = "https://api.manifold.markets/v0"

def _get_json(endpoint: str) -> Optional[dict]:
    """Helper to GET an endpoint and return json if request succeeds."""
    url = f"{API_BASE}/{endpoint}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.ok:
            return resp.json()
    except Exception:
        pass
    return None

def resolve_entity(term: str) -> Optional[Tuple[str, str]]:
    """Resolve a slug/username/ID to (id, type)."""
    slug = term.strip().rstrip('/')
    slug_part = slug.split('/')[-1]

    # User by username
    data = _get_json(f"user/{slug}")
    if data:
        return data.get("id"), "user"

    # User by id
    data = _get_json(f"user/by-id/{slug}")
    if data:
        return data.get("id"), "user"

    # Group by slug
    data = _get_json(f"group/{slug}")
    if data:
        return data.get("id"), "group"

    # Group by id
    data = _get_json(f"group/by-id/{slug}")
    if data:
        return data.get("id"), "group"

    # Market by slug (allow username/slug style)
    data = _get_json(f"slug/{slug_part}")
    if data:
        return data.get("id"), "market"

    # Market by id
    data = _get_json(f"market/{slug}")
    if data:
        return data.get("id"), "market"

    return None


def resolve_entity_with_data(term: str) -> Optional[Tuple[str, str, Dict[str, Any]]]:
    """Resolve a slug/username/ID to (id, type, data)."""
    slug = term.strip().rstrip('/')
    slug_part = slug.split('/')[-1]

    endpoints = [
        (f"user/{slug}", "user"),
        (f"user/by-id/{slug}", "user"),
        (f"group/{slug}", "group"),
        (f"group/by-id/{slug}", "group"),
        (f"slug/{slug_part}", "market"),
        (f"market/{slug}", "market"),
    ]

    for endpoint, entity_type in endpoints:
        data = _get_json(endpoint)
        if data:
            return data.get("id"), entity_type, data

    return None

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python -m src.utils.entity_resolver <slug_or_username_or_id>")
        sys.exit(1)

    query = sys.argv[1]
    result = resolve_entity_with_data(query)
    if result:
        entity_id, entity_type, data = result
        print(f"type: {entity_type}")
        print(f"id: {entity_id}")

        url = data.get("url")
        if not url:
            if entity_type == "user" and data.get("username"):
                url = f"https://manifold.markets/{data['username']}"
            elif entity_type == "group" and data.get("slug"):
                url = f"https://manifold.markets/group/{data['slug']}"
            elif entity_type == "market" and data.get("slug"):
                url = f"https://manifold.markets/{data['slug']}"
        if url:
            print(f"url: {url}")

        if entity_type == "user":
            print(f"username: {data.get('username')}")
            print(f"name: {data.get('name')}")
        elif entity_type == "group":
            print(f"name: {data.get('name')}")
            print(f"slug: {data.get('slug')}")
        elif entity_type == "market":
            print(f"question: {data.get('question')}")
            print(
                f"outcome_type: {data.get('outcomeType') or data.get('outcome_type')}"
            )
            if data.get('outcomeType') == 'MULTIPLE_CHOICE' or data.get('outcome_type') == 'MULTIPLE_CHOICE':
                answers = data.get('answers') or []
                for ans in answers:
                    text = ans.get('text')
                    aid = ans.get('id')
                    print(f"{text}: {aid}")
    else:
        print("Entity not found")
