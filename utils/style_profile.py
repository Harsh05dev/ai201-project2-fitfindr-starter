"""
Persist user style preferences across sessions (stretch: style profile memory).
Stored as JSON in data/style_profile.json — not committed if gitignored, but
we use a default path in the data folder for the demo.
"""

import json
import os

_PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "style_profile.json")


def load_style_profile() -> dict:
    """Load saved style profile or return empty template."""
    if not os.path.exists(_PROFILE_PATH):
        return {"preferred_styles": [], "preferred_size": None, "typical_max_price": None, "notes": []}
    with open(_PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_style_profile(profile: dict) -> None:
    with open(_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)


def update_style_profile_from_session(session: dict) -> None:
    """Merge learnings from a successful session into the profile."""
    if session.get("error") or not session.get("selected_item"):
        return

    profile = load_style_profile()
    item = session["selected_item"]
    parsed = session.get("parsed", {})

    for tag in item.get("style_tags", []):
        if tag not in profile["preferred_styles"]:
            profile["preferred_styles"].append(tag)

    if parsed.get("size"):
        profile["preferred_size"] = parsed["size"]
    if parsed.get("max_price"):
        profile["typical_max_price"] = parsed["max_price"]

    note = f"Liked {item['title']} (${item['price']})"
    if note not in profile["notes"]:
        profile["notes"].append(note)

    save_style_profile(profile)


def apply_style_profile_to_parsed(parsed: dict) -> tuple[dict, str | None]:
    """
    Fill in missing parsed fields from saved profile.
    Returns (updated_parsed, message_if_profile_used).
    """
    profile = load_style_profile()
    if not profile["preferred_styles"] and not profile.get("preferred_size"):
        return parsed, None

    used = []
    if not parsed.get("size") and profile.get("preferred_size"):
        parsed["size"] = profile["preferred_size"]
        used.append(f"size {profile['preferred_size']}")
    if not parsed.get("max_price") and profile.get("typical_max_price"):
        parsed["max_price"] = profile["typical_max_price"]
        used.append(f"max ${profile['typical_max_price']}")

    if used:
        return parsed, f"Applied your saved style profile: {', '.join(used)}."
    return parsed, None
