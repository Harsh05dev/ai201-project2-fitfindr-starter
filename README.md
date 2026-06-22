# FitFindr

FitFindr is a multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural-language query, the agent searches mock listings, checks price fairness and trends, suggests outfits using your wardrobe, and generates a shareable fit card.

**Run the app:**
```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Add GROQ_API_KEY to .env
python app.py
```

**Run tests:**
```bash
pytest tests/ -v
```

---

## Tool Inventory

### Required tools (`tools.py`)

| Tool | Inputs | Returns | Purpose |
|------|--------|---------|---------|
| `search_listings(description, size, max_price)` | `description` (str), `size` (str \| None), `max_price` (float \| None) | `list[dict]` — each dict has `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Sorted by relevance. Empty list if no match. | Search mock secondhand listings with keyword scoring plus optional size/price filters. |
| `suggest_outfit(new_item, wardrobe, trends, style_profile)` | `new_item` (dict), `wardrobe` (dict with `items` list), `trends` (str \| None), `style_profile` (dict \| None) | `str` — 1–2 outfit suggestions naming wardrobe pieces when available; general styling advice if wardrobe is empty. | LLM-powered outfit ideas that incorporate the found item and user context. |
| `create_fit_card(outfit, new_item)` | `outfit` (str), `new_item` (dict) | `str` — 2–4 sentence casual social caption, or error message string if outfit is empty. | Generate a shareable Instagram/TikTok-style caption. |

### Stretch tools

| Tool | Inputs | Returns | Purpose |
|------|--------|---------|---------|
| `compare_price(item)` | `item` (dict) | `str` — verdict (Good deal / Fair price / Above average) with avg/range vs comparable listings in same category with overlapping style tags. | Help user judge if a listing price is fair. |
| `check_trends(size, category)` | `size` (str \| None), `category` (str \| None) | `str` — trending styles and hot tags for the user's size bucket. | Surface mock Depop/Pinterest tag trends from `data/trends.json` to influence outfit suggestions. |

---

## Planning Loop

The agent (`agent.py` → `run_agent`) uses **conditional sequential logic** — not a fixed pipeline.

1. **Parse query** with regex → `session["parsed"]` (`description`, `size`, `max_price`).
2. **Apply style profile** (stretch) — if user omits size/budget, fill from `data/style_profile.json`.
3. **Search with retry** (`_search_with_retry`):
   - Call `search_listings` with full filters.
   - **If empty and size was set** → retry without size, set `search_retry_note`.
   - **If still empty and max_price was set** → retry without price limit too.
   - **If still empty** → set `session["error"]` with actionable advice and **return early** (does NOT call `suggest_outfit` or `create_fit_card`).
4. **On results** → `session["selected_item"] = results[0]`.
5. **Call `compare_price`** and **`check_trends`** (stretch) — store in session.
6. **Call `suggest_outfit`** with `selected_item`, wardrobe, trends, and style profile.
7. **Call `create_fit_card`** with `outfit_suggestion` and `selected_item`.
8. **Save style profile** after successful run.

**When `search_listings` returns no results (even after retry):** The agent sets a specific error message telling the user what failed and what to try (broader keywords, remove size filter, raise budget). `outfit_suggestion` and `fit_card` remain `None`.

**Adaptiveness demo:** Compare `"vintage graphic tee under $30"` (happy path, all 5 tools) vs `"designer ballgown size XXS under $5"` (error only, no downstream tools).

---

## State Management

One `session` dict per interaction:

| Field | When set | Passed to |
|-------|----------|-----------|
| `parsed` | After regex parse | `search_listings` |
| `search_results` | After search | `selected_item = results[0]` |
| `selected_item` | Top search result | `compare_price`, `check_trends`, `suggest_outfit`, `create_fit_card` |
| `trends` | After `check_trends` | `suggest_outfit` prompt |
| `outfit_suggestion` | After `suggest_outfit` | `create_fit_card` |
| `fit_card` | After `create_fit_card` | UI output |
| `error` | On early exit | UI first panel |

The UI shows `[State] selected_item id: ...` and notes that outfit/fit card use the same session values — no re-entry.

---

## Error Handling

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No matches (even after retry) | `session["error"]`: *"No listings found for 'designer ballgown' (size XXS, max $5.0). Try broader keywords..."* — stops before other tools. **Tested:** `python agent.py` no-results path. |
| `suggest_outfit` | Empty wardrobe | Returns general styling advice (not an error). Agent continues to fit card. **Tested:** `pytest tests/test_tools.py::test_suggest_outfit_empty_wardrobe`. |
| `suggest_outfit` | LLM API failure | Returns *"Could not generate outfit suggestions right now..."* — stored in session, fit card may still run. |
| `create_fit_card` | Empty outfit string | Returns *"Cannot create a fit card without an outfit suggestion."* **Tested:** `pytest tests/test_tools.py::test_create_fit_card_empty_outfit`. |

**Deliberate failure to demo:** Use example query `"designer ballgown size XXS under $5"` in the Gradio UI — only the listing panel shows an error; outfit and fit card panels stay empty.

---

## Stretch Features

### Price comparison (`compare_price`)
Compares item price to same-category listings with overlapping `style_tags`. Shows avg, range, and verdict. Displayed in listing panel under "💰 Price check".

### Style profile memory (`utils/style_profile.py`)
After each successful run, saves preferred styles, size, and budget to `data/style_profile.json`. On the next query, missing size/budget are auto-filled and noted in the UI ("Applied your saved style profile...").

**Demo:** Run `"vintage graphic tee under $30"` once, then `"graphic tee"` — second run applies saved size/budget without re-entry.

### Trend awareness (`check_trends`)
Reads mock public tag data from `data/trends.json` (Depop/Pinterest-style snapshot). Trends are passed into `suggest_outfit` so outfit ideas reflect current styles.

### Retry with fallback (`_search_with_retry`)
If zero results with size filter, automatically retries without size and tells the user what was adjusted.

**Demo:** `"vintage graphic tee size XXS under $30"` → retry note appears, results found.

---

## Interaction Walkthrough

**User query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers."

**Step 1 — `search_listings`**
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why: User asked what's available — search runs first.
- Output: List of matches; top pick stored as `session["selected_item"]` (e.g., Y2K Baby Tee or Vintage Band Tee).

**Step 2 — `compare_price` + `check_trends` (stretch)**
- Input: `selected_item`, size/category from parse
- Why: Give price context and current trends before styling.
- Output: Price verdict string + trend tags in listing panel.

**Step 3 — `suggest_outfit`**
- Input: `new_item=session["selected_item"]`, `wardrobe=get_example_wardrobe()`, `trends=session["trends"]`
- Why: User asked how to style it; uses the exact item from step 1.
- Output: Outfit text referencing baggy jeans and chunky sneakers from wardrobe.

**Step 4 — `create_fit_card`**
- Input: `outfit=session["outfit_suggestion"]`, `new_item=session["selected_item"]`
- Why: Final shareable caption.
- Output: Casual OOTD caption in fit card panel.

**Final output:** Three UI panels — listing (with price check + trends), outfit idea, fit card.

---

## Spec Reflection

**One way planning.md helped:** The conditional planning loop spec ("if `search_results` empty → return early") prevented me from wiring all three tools in a fixed sequence. I implemented the branch in `run_agent` exactly as diagrammed.

**One divergence:** I added optional `trends` and `style_profile` parameters to `suggest_outfit` beyond the original three-parameter signature. This was necessary for stretch features to visibly influence outfit output without separate agent-side prompt building.

---

## AI Usage

**Instance 1 — Tool implementations:** I gave Cursor the Tool 1–3 blocks from `planning.md` plus `data_loader.py` and asked it to implement `search_listings`, `suggest_outfit`, and `create_fit_card`. I verified keyword scoring matched the spec, confirmed empty-list behavior for search, and ran `pytest tests/test_tools.py` before accepting. I overrode the default temperature for `create_fit_card` to 0.9 after noticing identical captions on repeat runs.

**Instance 2 — Planning loop:** I shared the Architecture diagram and Planning Loop + State Management sections and asked for `run_agent()` and `handle_query()`. I revised the generated retry logic to try removing size before removing price (clearer user messaging) and added `format_listing_panel()` to surface stretch tool output and state IDs for the demo video.

---

## Project Structure

```
├── agent.py              # Planning loop + query parsing
├── app.py                # Gradio UI
├── tools.py              # All tool functions
├── planning.md           # Pre-implementation spec
├── data/
│   ├── listings.json
│   ├── wardrobe_schema.json
│   ├── trends.json
│   └── style_profile.json  # Created at runtime
├── utils/
│   ├── data_loader.py
│   └── style_profile.py
└── tests/
    ├── test_tools.py
    └── test_agent.py
```
