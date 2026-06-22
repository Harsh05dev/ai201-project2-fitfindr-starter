from agent import run_agent, parse_query
from tools import compare_price, check_trends, search_listings
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def test_parse_query_extracts_price_and_description():
    parsed = parse_query("vintage graphic tee under $30, size M")
    assert parsed["max_price"] == 30.0
    assert parsed["size"] == "M"
    assert "graphic" in parsed["description"].lower()


def test_agent_happy_path_uses_all_tools():
    session = run_agent("vintage graphic tee under $30", get_example_wardrobe(), use_style_profile=False)
    assert session["error"] is None
    assert session["selected_item"] is not None
    assert session["outfit_suggestion"]
    assert session["fit_card"]
    assert session["price_assessment"]
    assert session["trends"]


def test_agent_no_results_skips_downstream_tools():
    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe(), use_style_profile=False)
    assert session["error"] is not None
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None


def test_agent_retry_loosens_size_filter():
    session = run_agent("vintage graphic tee size XXS under $30", get_example_wardrobe(), use_style_profile=False)
    assert session["error"] is None or session.get("search_retry_note")
    if not session["error"]:
        assert session["search_retry_note"] is not None


def test_state_passes_between_tools():
    session = run_agent("vintage graphic tee under $50", get_example_wardrobe(), use_style_profile=False)
    assert session["selected_item"]["id"] == session["search_results"][0]["id"]


def test_compare_price_returns_assessment():
    results = search_listings("graphic tee", size=None, max_price=50)
    assessment = compare_price(results[0])
    assert "vs comparable" in assessment.lower() or "deal" in assessment.lower()


def test_check_trends_returns_tags():
    trends = check_trends(size="M", category="tops")
    assert "Trending" in trends
    assert "grunge" in trends or "streetwear" in trends
