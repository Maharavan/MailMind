"""Trello API helpers for TaskAgent."""
import logging

import requests

from config.settings import settings

logger = logging.getLogger(__name__)


def get_existing_cards() -> list[dict]:
    """Return all cards currently in the configured Trello list."""
    url = f"https://api.trello.com/1/lists/{settings.TRELLO_LIST_ID}/cards"
    try:
        response = requests.get(
            url,
            params={"key": settings.TRELLO_API_KEY, "token": settings.TRELLO_API_TOKEN},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning("Failed to fetch Trello cards: %s", str(e))
        return []


def create_trello_card(name: str, desc: str, due: str) -> dict | None:
    """
    Create a Trello card in the configured list.

    Returns the API response dict on success, or None if the request fails.
    """
    url = "https://api.trello.com/1/cards"
    payload = {
        "key": settings.TRELLO_API_KEY,
        "token": settings.TRELLO_API_TOKEN,
        "idList": settings.TRELLO_LIST_ID,
        "name": name,
        "desc": desc,
        "due": due,
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.warning("Failed to create Trello card: %s", str(e))
        return None
