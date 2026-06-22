"""
app.py — Gradio interface for FitFindr.
"""

import gradio as gr

from agent import run_agent, format_listing_panel
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str]:
    if not user_query or not user_query.strip():
        return "Please enter what you're looking for.", "", ""

    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == "Example wardrobe"
        else get_empty_wardrobe()
    )

    session = run_agent(user_query, wardrobe)

    if session.get("error"):
        return format_listing_panel(session), "", ""

    listing_text = format_listing_panel(session)
    outfit = session.get("outfit_suggestion") or ""
    fit_card = session.get("fit_card") or ""

    outfit_with_state = (
        f"{outfit}\n\n[State] outfit from selected_item '{session['selected_item']['title']}'"
        if outfit else ""
    )
    fitcard_with_state = (
        f"{fit_card}\n\n[State] fit card uses outfit_suggestion above + item id {session['selected_item']['id']}"
        if fit_card else ""
    )

    return listing_text, outfit_with_state, fitcard_with_state


EXAMPLE_QUERIES = [
    "vintage graphic tee under $30",
    "90s track jacket in size M",
    "flowy midi skirt under $40",
    "black combat boots size 8",
    "vintage graphic tee size XXS under $30",
    "designer ballgown size XXS under $5",
]


def build_interface():
    with gr.Blocks(title="FitFindr") as demo:
        gr.Markdown("""
# FitFindr 🛍️
Find secondhand pieces and get outfit ideas based on your wardrobe.
Describe what you're looking for — include size and price if you want to filter.
        """)

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe",
                scale=1,
            )

        submit_btn = gr.Button("Find it", variant="primary")

        with gr.Row():
            listing_output = gr.Textbox(
                label="🛍️ Top listing found",
                lines=10,
                interactive=False,
            )
            outfit_output = gr.Textbox(
                label="👗 Outfit idea",
                lines=10,
                interactive=False,
            )
            fitcard_output = gr.Textbox(
                label="✨ Your fit card",
                lines=10,
                interactive=False,
            )

        gr.Examples(
            examples=[[q, "Example wardrobe"] for q in EXAMPLE_QUERIES],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=[listing_output, outfit_output, fitcard_output],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
