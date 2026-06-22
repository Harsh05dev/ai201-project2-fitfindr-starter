# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock secondhand listings dataset (`data/listings.json`) for items matching a natural-language description, optional size, and optional max price. Returns matching listing dicts sorted by keyword relevance (best match first).

**Input parameters:**
- `description` (str): Keywords describing what the user wants (e.g., `"vintage graphic tee"`). Matched against listing `title`, `description`, `category`, and `style_tags` via case-insensitive keyword overlap scoring.
- `size` (str | None): Size filter, or `None` to skip. Case-insensitive substring match against listing `size` (e.g., `"M"` matches `"S/M"` or `"M"`).
- `max_price` (float | None): Maximum price inclusive, or `None` to skip price filtering.

**What it returns:**
A `list[dict]` of matching listing objects (may be empty). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list[str]), `size`, `condition`, `price` (float), `colors` (list[str]), `brand` (str | None), `platform` (str). Sorted by relevance score descending. Returns `[]` — never raises — when nothing matches.

**What happens if it fails or returns nothing:**
The planning loop checks `if not search_results`. It sets `session["error"]` to a user-facing message such as: *"No listings matched your search. Try broadening your keywords (e.g., 'graphic tee' instead of 'vintage band tee'), removing the size filter, or raising your max price."* It returns the session immediately without calling `suggest_outfit` or `create_fit_card`.

---

### Tool 2: suggest_outfit

**What it does:**
Given a specific thrift listing and the user's wardrobe, calls Groq (`llama-3.3-70b-versatile`) to suggest one or two complete outfit combinations that incorporate the new item with pieces from the wardrobe (or general styling advice if the wardrobe is empty).

**Input parameters:**
- `new_item` (dict): A single listing dict from `search_listings` (the item the user is considering buying). Must include at least `title`, `description`, `category`, `style_tags`, `colors`, and `price`.
- `wardrobe` (dict): Wardrobe object with an `items` key containing a list of wardrobe item dicts. Each item has `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. May be empty (`items: []`).

**What it returns:**
A non-empty `str` with 1–2 outfit suggestions in plain language. Names specific wardrobe pieces when available (e.g., "pair with your baggy straight-leg jeans and chunky white sneakers"). If the wardrobe is empty, returns general styling advice (what categories/colors/vibes pair well) instead of referencing named pieces.

**What happens if it fails or returns nothing:**
- **Empty wardrobe:** Not a hard failure — the tool still returns general styling advice via the LLM. The agent proceeds to `create_fit_card`.
- **LLM API error:** Returns a string like `"Could not generate outfit suggestions right now. Try again in a moment."` The agent stores this in `session["outfit_suggestion"]` and still attempts `create_fit_card` unless the string is clearly an error (agent may set `session["error"]` if outfit is unusable).

---

### Tool 3: create_fit_card

**What it does:**
Calls Groq (`llama-3.3-70b-versatile`, temperature 0.9) to generate a short, casual, shareable outfit caption — like an Instagram/TikTok OOTD post — based on the outfit suggestion and the thrifted item details.

**Input parameters:**
- `outfit` (str): The outfit suggestion string from `suggest_outfit`.
- `new_item` (dict): The listing dict for the thrifted item (needs `title`, `price`, `platform` at minimum).

**What it returns:**
A `str` of 2–4 sentences usable as a social caption. Mentions item name, price, and platform naturally. Varies in wording across runs (higher temperature). If `outfit` is empty or whitespace-only, returns an error message string instead of calling the LLM.

**What happens if it fails or returns nothing:**
- **Empty outfit input:** Returns `"Cannot create a fit card without an outfit suggestion. Run suggest_outfit first."` — no exception raised.
- **LLM API error:** Returns `"Could not generate a fit card right now. Your outfit suggestion is still saved above."`

---

### Additional Tools (if any)

#### Tool 4: compare_price (stretch)

**What it does:** Compares a listing's price to comparable items in the same category with overlapping style tags.

**Input parameters:**
- `item` (dict): Listing dict with `id`, `category`, `style_tags`, `price`.

**What it returns:** `str` — verdict (Good deal / Fair price / Above average) with average price, range, and count of comparables.

**Failure mode:** If item data incomplete, returns error string. Agent still continues to outfit suggestion.

#### Tool 5: check_trends (stretch)

**What it does:** Reads mock Depop/Pinterest tag data from `data/trends.json` and returns trending styles for the user's size bucket.

**Input parameters:**
- `size` (str | None): Size string for bucket lookup.
- `category` (str | None): Optional category for context in the message.

**What it returns:** `str` describing trending styles and hot tags.

**Failure mode:** If file missing, returns "Trend data temporarily unavailable." Agent continues.

#### Style profile memory (stretch — `utils/style_profile.py`)

Persists `preferred_styles`, `preferred_size`, `typical_max_price` to `data/style_profile.json` after successful runs. On next query, fills missing parsed fields and shows a note in the UI.

#### Retry with fallback (stretch — `_search_with_retry` in `agent.py`)

If initial `search_listings` returns `[]`, retry without size filter, then without price limit, setting `search_retry_note` explaining what was adjusted.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The agent uses a **conditional sequential loop** — not a fixed pipeline. Each step checks the previous step's output before proceeding.

1. **Initialize** `session = _new_session(query, wardrobe)`.
2. **Parse query** with regex to extract `description`, `size`, and `max_price` from the natural-language string. Store in `session["parsed"]`. Parsing uses patterns like `under $30` / `max $30` for price, `size M` / `size 8` for size, and the remaining text (minus price/size phrases) as description.
3. **Apply style profile** (stretch) — fill missing size/budget from saved profile.
4. **Call `search_listings` with retry** (`_search_with_retry`) → store in `session["search_results"]`.
   - **Branch:** If still empty after retries → set `session["error"]` → **return early**.
5. **Select top result** → `session["selected_item"]`.
6. **Call `compare_price` and `check_trends`** (stretch) → store assessments.
7. **Call `suggest_outfit`** with selected item, wardrobe, trends, style profile.
8. **Call `create_fit_card`** → store fit card.
9. **Save style profile** and return session.

**Done when:** All three tools succeed, or an early-return branch fires (empty search results).

---

## State Management

**How does information from one tool get passed to the next?**

A single `session` dict is the source of truth for one user interaction:

| Field | Set when | Used by |
|-------|----------|---------|
| `query` | Init | Parsing |
| `parsed` | After regex parse | `search_listings` inputs |
| `search_results` | After search | Selecting `selected_item` |
| `selected_item` | After search (top result) | `suggest_outfit`, `create_fit_card` |
| `wardrobe` | Init (from UI or caller) | `suggest_outfit` |
| `outfit_suggestion` | After suggest | `create_fit_card` |
| `fit_card` | After fit card | Returned to UI |
| `error` | On early exit or failure | UI first panel |

The agent never re-prompts the user mid-flow. `selected_item` from search flows directly into `suggest_outfit(new_item=session["selected_item"], ...)`, and `outfit_suggestion` flows into `create_fit_card(outfit=session["outfit_suggestion"], ...)`.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Set `session["error"]`: *"No listings found for '[description]' (size: [size], max $[price]). Try removing the size filter, using broader keywords like 'graphic tee', or raising your budget."* Return session; `selected_item`, `outfit_suggestion`, and `fit_card` stay `None`. |
| suggest_outfit | Wardrobe is empty | Tool returns general styling advice (not an error). Agent continues to `create_fit_card`. UI shows outfit panel with generic pairing ideas. |
| create_fit_card | Outfit input is missing or incomplete | Tool returns: *"Cannot create a fit card without an outfit suggestion."* Agent stores this in `fit_card`; user sees the message in the fit card panel. |

---

## Architecture

```mermaid
flowchart TD
    U[User Query] --> PL[Planning Loop]
    PL --> P[Parse query → session.parsed]
    P --> SL[search_listings]
    SL -->|results = []| ERR1[session.error = helpful message]
    ERR1 --> RET1[Return session early]
    SL -->|results found| SEL[session.selected_item = results0]
    SEL --> SO[suggest_outfit]
    SO --> OS[session.outfit_suggestion]
    OS --> FC[create_fit_card]
    FC --> FCARD[session.fit_card]
    FCARD --> RET2[Return session]
    W[Wardrobe dict] --> SO
```

ASCII equivalent:

```
User query
    │
    ▼
Planning Loop ───────────────────────────────────────────┐
    │                                                    │
    ├─► Parse query → session["parsed"]                  │
    │                                                    │
    ├─► search_listings(description, size, max_price)    │
    │       │ results=[]                                 │
    │       ├──► [ERROR] "No listings found..." → return │
    │       │                                            │
    │       │ results=[item, ...]                        │
    │       ▼                                            │
    │   Session: selected_item = results[0]              │
    │       │                                            │
    ├─► suggest_outfit(selected_item, wardrobe)          │
    │       │                                            │
    │   Session: outfit_suggestion = "..."               │
    │       │                                            │
    └─► create_fit_card(outfit_suggestion, selected_item)│
            │                                            │
        Session: fit_card = "..."                        │
            │                                            └─ error path returns here
            ▼
        Return session
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **Tool:** Cursor (Claude)
- **Input:** Tool 1 block from this file (inputs, return value, failure mode) + `utils/data_loader.py` docstring for `load_listings()`
- **Expected output:** `search_listings()` in `tools.py` with keyword scoring, size/price filters, empty list on no match
- **Verification:** Run `pytest tests/test_tools.py::test_search_*` and manual `python -c "from tools import search_listings; print(search_listings('vintage graphic tee', size=None, max_price=50))"` — confirm list length > 0 and all prices ≤ max

- **Tool:** Cursor (Claude)
- **Input:** Tool 2 block + wardrobe schema example
- **Expected output:** `suggest_outfit()` using Groq with separate prompts for empty vs populated wardrobe
- **Verification:** Test with `get_example_wardrobe()` and `get_empty_wardrobe()` — both return non-empty strings, no exceptions

- **Tool:** Cursor (Claude)
- **Input:** Tool 3 block + temperature note
- **Expected output:** `create_fit_card()` with empty-outfit guard and temp=0.9
- **Verification:** Call twice with same inputs — outputs should differ; call with `outfit=""` — returns error string not exception

**Milestone 4 — Planning loop and state management:**

- **Tool:** Cursor (Claude)
- **Input:** Architecture diagram + Planning Loop + State Management sections from this file
- **Expected output:** `run_agent()` in `agent.py` and `handle_query()` in `app.py`
- **Verification:** Run `python agent.py` — happy path prints title/outfit/fit_card; no-results path prints error and `fit_card` is None. Print `session["selected_item"]["id"]` to confirm same object flows to suggest_outfit.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
- **Tool:** `search_listings`
- **Input:** `description="vintage graphic tee"`, `size=None`, `max_price=30.0` (parsed from query via regex)
- **Why:** User asked what's available — search must run first before styling.
- **Output:** List of 3+ matches; top result likely `lst_033` "Vintage Band Tee — Faded Grey" ($19, depop, size L) or `lst_006` "Graphic Tee — 2003 Tour Bootleg Style" ($24). Agent sets `session["selected_item"]` to `results[0]`.

**Step 2:**
- **Tool:** `suggest_outfit`
- **Input:** `new_item=session["selected_item"]`, `wardrobe=get_example_wardrobe()` (baggy jeans w_001, chunky sneakers w_007, etc.)
- **Why:** User asked how to style it; we have a found item and wardrobe context.
- **Output:** e.g., *"Pair the faded band tee with your baggy straight-leg jeans and chunky white sneakers for a classic 90s grunge look. Roll the sleeves once and half-tuck the front for shape."* Stored in `session["outfit_suggestion"]`.

**Step 3:**
- **Tool:** `create_fit_card`
- **Input:** `outfit=session["outfit_suggestion"]`, `new_item=session["selected_item"]`
- **Why:** Final deliverable — shareable caption for the complete look.
- **Output:** e.g., *"thrifted this faded band tee off depop for $19 and honestly it was made for my baggy jeans + chunky sneakers 🖤 full fit in my stories"*

**Final output to user:**
Three UI panels: (1) formatted listing details for the top match, (2) outfit suggestion text, (3) fit card caption. `session["error"]` is `None`.

**Error path example:** Query `"designer ballgown size XXS under $5"` → `search_listings` returns `[]` → agent sets error message, returns without calling `suggest_outfit` or `create_fit_card`.

---

## FitFindr Overview (Milestone 1)

FitFindr is a multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. A natural-language query triggers a planning loop: first `search_listings` finds matching items from mock data; if results exist, `suggest_outfit` combines the top pick with the user's wardrobe via an LLM; then `create_fit_card` generates a shareable social caption. If search returns nothing, the agent stops early with actionable feedback instead of calling downstream tools with empty input.
