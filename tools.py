"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

_TRENDS_PATH = os.path.join(os.path.dirname(__file__), "data", "trends.json")


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    listings = load_listings()
    keywords = [w.lower() for w in description.split() if len(w) > 1]

    filtered = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue
        filtered.append(listing)

    if not keywords:
        return filtered

    scored = []
    for listing in filtered:
        searchable = " ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing["style_tags"]),
        ]).lower()
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(
    new_item: dict,
    wardrobe: dict,
    trends: str | None = None,
    style_profile: dict | None = None,
) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    items = wardrobe.get("items", [])
    title = new_item.get("title", "this item")
    description = new_item.get("description", "")
    style_tags = ", ".join(new_item.get("style_tags", []))
    colors = ", ".join(new_item.get("colors", []))

    try:
        client = _get_groq_client()
    except ValueError:
        return "Could not generate outfit suggestions right now. Try again in a moment."

    trend_block = f"\nCurrent trends to consider: {trends}" if trends else ""
    profile_block = ""
    if style_profile and style_profile.get("preferred_styles"):
        profile_block = f"\nUser's saved style preferences: {', '.join(style_profile['preferred_styles'])}"

    if not items:
        prompt = f"""You are a personal stylist. A user found this thrifted item but has no wardrobe saved yet.

Item: {title}
Description: {description}
Style tags: {style_tags}
Colors: {colors}

Suggest 1-2 complete outfit ideas using general categories (e.g., "wide-leg jeans", "chunky sneakers") — not specific owned pieces. Keep it practical and under 150 words.{trend_block}{profile_block}"""
    else:
        wardrobe_lines = "\n".join(
            f"- {item['name']} ({item['category']}, {', '.join(item['colors'])})"
            for item in items
        )
        prompt = f"""You are a personal stylist. Suggest 1-2 complete outfits using the new thrift find AND specific pieces from the user's wardrobe.

New item: {title}
Description: {description}
Style tags: {style_tags}
Colors: {colors}

User's wardrobe:
{wardrobe_lines}

Name specific wardrobe pieces in your suggestions. Keep it practical and under 150 words.{trend_block}{profile_block}"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300,
        )
        text = response.choices[0].message.content.strip()
        return text if text else "Could not generate outfit suggestions right now. Try again in a moment."
    except Exception:
        return "Could not generate outfit suggestions right now. Try again in a moment."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Cannot create a fit card without an outfit suggestion. Run suggest_outfit first."

    title = new_item.get("title", "thrift find")
    price = new_item.get("price", "?")
    platform = new_item.get("platform", "thrift app")

    try:
        client = _get_groq_client()
    except ValueError:
        return "Could not generate a fit card right now. Your outfit suggestion is still saved above."

    prompt = f"""Write a casual Instagram/TikTok outfit caption (2-4 sentences) for this thrifted look.

Item: {title} — ${price} on {platform}
Outfit suggestion: {outfit}

Rules:
- Sound like a real person posting an OOTD, not a product description
- Mention the item name, price, and platform naturally once each
- Capture the vibe in specific terms
- Use casual tone, maybe one emoji
- Do NOT use hashtags"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=200,
        )
        text = response.choices[0].message.content.strip()
        return text if text else "Could not generate a fit card right now. Your outfit suggestion is still saved above."
    except Exception:
        return "Could not generate a fit card right now. Your outfit suggestion is still saved above."


# ── Stretch Tool 4: compare_price ─────────────────────────────────────────────

def compare_price(item: dict) -> str:
    """
    Estimate whether an item's price is fair based on comparable listings.

    Args:
        item: A listing dict with category, style_tags, and price.

    Returns:
        A string assessment (fair deal / good deal / above average) with reasoning.
    """
    if not item or "price" not in item:
        return "Cannot compare price — item data is incomplete."

    listings = load_listings()
    category = item.get("category")
    tags = set(item.get("style_tags", []))
    price = item["price"]

    comparables = [
        lst for lst in listings
        if lst["id"] != item.get("id")
        and lst.get("category") == category
        and tags.intersection(lst.get("style_tags", []))
    ]

    if len(comparables) < 2:
        comparables = [lst for lst in listings if lst["id"] != item.get("id") and lst.get("category") == category]

    if not comparables:
        return f"No comparable listings in the dataset. ${price:.2f} may still be reasonable for this category."

    prices = [lst["price"] for lst in comparables]
    avg_price = sum(prices) / len(prices)
    low, high = min(prices), max(prices)

    if price <= avg_price * 0.85:
        verdict = "Good deal"
    elif price <= avg_price * 1.15:
        verdict = "Fair price"
    else:
        verdict = "Above average"

    return (
        f"{verdict}: ${price:.2f} vs comparable {category} listings "
        f"(avg ${avg_price:.2f}, range ${low:.2f}–${high:.2f} across {len(comparables)} items). "
        f"Based on shared style tags and category in our mock dataset."
    )


# ── Stretch Tool 5: check_trends ────────────────────────────────────────────

def check_trends(size: str | None = None, category: str | None = None) -> str:
    """
    Surface trending styles from mock public fashion platform data.

    Args:
        size: Optional size string (uses first letter/size bucket).
        category: Optional category filter for context.

    Returns:
        A string describing current trends relevant to the user's size range.
    """
    try:
        with open(_TRENDS_PATH, "r", encoding="utf-8") as f:
            trends_data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return "Trend data temporarily unavailable."

    size_key = "default"
    if size:
        upper = size.upper()
        for key in ("S", "M", "L", "XL"):
            if key in upper:
                size_key = key if key != "XL" else "L"
                break

    size_trends = trends_data.get("trends_by_size", {}).get(size_key) or trends_data["trends_by_size"]["default"]
    hot = trends_data.get("hot_tags_2026", [])
    cat_note = f" for {category}" if category else ""

    return (
        f"Trending in size {size or 'your range'}{cat_note}: {', '.join(size_trends)}. "
        f"Hot tags right now: {', '.join(hot[:4])}. "
        f"(Source: mock Depop/Pinterest tag snapshot in data/trends.json)"
    )
