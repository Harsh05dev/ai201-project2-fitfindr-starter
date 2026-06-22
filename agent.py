"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.
"""

import re

from tools import (
    search_listings,
    suggest_outfit,
    create_fit_card,
    compare_price,
    check_trends,
)
from utils.style_profile import (
    load_style_profile,
    apply_style_profile_to_parsed,
    update_style_profile_from_session,
)


def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "price_assessment": None,
        "trends": None,
        "search_retry_note": None,
        "style_profile_note": None,
        "error": None,
    }


def parse_query(query: str) -> dict:
    """Extract description, size, and max_price from natural language using regex."""
    text = query.strip()
    max_price = None
    size = None

    price_match = re.search(
        r"(?:under|below|max|less than)\s*\$?\s*(\d+(?:\.\d+)?)",
        text,
        re.IGNORECASE,
    )
    if price_match:
        max_price = float(price_match.group(1))

    size_match = re.search(
        r"size\s+([A-Za-z0-9./\s-]+?)(?:\s+(?:under|below|max|,|$)|$)",
        text,
        re.IGNORECASE,
    )
    if size_match:
        size = size_match.group(1).strip().rstrip(".,;")

    description = text
    description = re.sub(
        r"(?:under|below|max|less than)\s*\$?\s*\d+(?:\.\d+)?",
        "",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"size\s+[A-Za-z0-9./\s-]+", "", description, flags=re.IGNORECASE)
    description = re.sub(
        r"\b(i mostly wear|what's out there|how would i style|what out there)\b.*",
        "",
        description,
        flags=re.IGNORECASE,
    )
    description = " ".join(description.split()).strip(" .,;?")

    if not description:
        description = text

    return {"description": description, "size": size, "max_price": max_price}


def _search_with_retry(parsed: dict) -> tuple[list[dict], str | None]:
    """
    Search listings; if empty, retry with loosened constraints.
    Returns (results, note_about_adjustments).
    """
    description = parsed["description"]
    size = parsed.get("size")
    max_price = parsed.get("max_price")

    results = search_listings(description, size=size, max_price=max_price)
    if results:
        return results, None

    notes = []

    if size is not None:
        results = search_listings(description, size=None, max_price=max_price)
        if results:
            notes.append("removed size filter")
            return results, "No exact size match — I " + " and ".join(notes) + " and found options."

    if max_price is not None:
        results = search_listings(description, size=None, max_price=None)
        if results:
            notes.append("removed price limit")
            return results, "No matches at your budget — I " + " and ".join(notes) + " and found options."

    if size is not None and max_price is not None:
        results = search_listings(description, size=None, max_price=None)
        if results:
            return results, "No matches with your filters — I removed size and price limits and found options."

    return [], None


def run_agent(query: str, wardrobe: dict, use_style_profile: bool = True) -> dict:
    session = _new_session(query, wardrobe)

    if not query or not query.strip():
        session["error"] = "Please enter what you're looking for (e.g., 'vintage graphic tee under $30, size M')."
        return session

    parsed = parse_query(query)
    style_profile = load_style_profile() if use_style_profile else {"preferred_styles": []}

    if use_style_profile:
        parsed, profile_note = apply_style_profile_to_parsed(parsed)
        session["style_profile_note"] = profile_note

    session["parsed"] = parsed

    results, retry_note = _search_with_retry(parsed)
    session["search_results"] = results
    session["search_retry_note"] = retry_note

    if not results:
        size_part = f"size {parsed['size']}, " if parsed.get("size") else ""
        price_part = f"max ${parsed['max_price']}" if parsed.get("max_price") else "your filters"
        session["error"] = (
            f"No listings found for '{parsed['description']}' ({size_part}{price_part}). "
            "Try broader keywords (e.g., 'graphic tee' instead of 'vintage band tee'), "
            "remove the size filter, or raise your budget."
        )
        return session

    session["selected_item"] = results[0]
    item = session["selected_item"]

    session["price_assessment"] = compare_price(item)
    session["trends"] = check_trends(
        size=parsed.get("size") or item.get("size"),
        category=item.get("category"),
    )

    session["outfit_suggestion"] = suggest_outfit(
        new_item=item,
        wardrobe=wardrobe,
        trends=session["trends"],
        style_profile=style_profile if use_style_profile else None,
    )

    session["fit_card"] = create_fit_card(session["outfit_suggestion"], item)

    if use_style_profile:
        update_style_profile_from_session(session)

    return session


def format_listing_panel(session: dict) -> str:
    """Format listing + stretch tool output for the UI."""
    if session.get("error"):
        parts = [session["error"]]
        if session.get("search_retry_note"):
            parts.append(session["search_retry_note"])
        if session.get("style_profile_note"):
            parts.append(session["style_profile_note"])
        return "\n\n".join(parts)

    item = session["selected_item"]
    lines = [
        f"**{item['title']}**",
        f"${item['price']:.2f} · {item['platform']} · {item['condition']} · Size {item['size']}",
        item["description"],
        f"Styles: {', '.join(item['style_tags'])}",
        f"Colors: {', '.join(item['colors'])}",
    ]
    if session.get("search_retry_note"):
        lines.append(f"\n⚠️ {session['search_retry_note']}")
    if session.get("style_profile_note"):
        lines.append(f"\n👤 {session['style_profile_note']}")
    if session.get("price_assessment"):
        lines.append(f"\n💰 Price check: {session['price_assessment']}")
    if session.get("trends"):
        lines.append(f"\n📈 Trends: {session['trends']}")
    lines.append(f"\n[State] selected_item id: {item['id']}")
    return "\n".join(lines)


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(format_listing_panel(session))
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")
        print(f"\nState check — same item flows to outfit: {session['selected_item']['id']}")

    print("\n\n=== No-results path (no retry possible) ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error: {session2['error']}")
    print(f"fit_card is None: {session2['fit_card'] is None}")
    print(f"outfit_suggestion is None: {session2['outfit_suggestion'] is None}")

    print("\n\n=== Retry path: strict size ===\n")
    session3 = run_agent(
        query="vintage graphic tee size XXS under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session3.get("search_retry_note"):
        print(f"Retry note: {session3['search_retry_note']}")
    if session3["error"]:
        print(f"Error: {session3['error']}")
    else:
        print(f"Found after retry: {session3['selected_item']['title']}")
