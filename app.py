import streamlit as st
import os
import re
from dotenv import load_dotenv
from pypdf import PdfReader
from google import genai
from fpdf import FPDF

# ----------------- SETUP -----------------
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("GEMINI_API_KEY is not set. Please add it to Streamlit Secrets.")
    st.stop()

client = genai.Client(api_key=API_KEY)

st.set_page_config(
    page_title="AI VC Startup Screener",
    layout="wide"
)

st.title("🚀 AI VC Startup Screening & IC Memo Generator")
st.caption(
    "Internal-style investment memos. Opinionated. Honest. No hallucinations."
)

MAX_DECK_MB = 10

# ----------------- HELPERS -----------------
def read_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text[:6000]  # hard cap for free-tier safety


def clean_memo_text(text: str) -> str:
    text = re.sub(r'(?<=\w)\s+(?=\w)', ' ', text)
    text = re.sub(r'(\d)\s+([a-zA-Z])', r'\1\2', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def normalize_for_pdf(text: str) -> str:
    replacements = {
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "•": "-",
        "→": "->",
        "≤": "<=",
        "≥": ">=",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def memo_to_pdf(text):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    for line in text.split("\n"):
        pdf.multi_cell(0, 6, line)
    return pdf


# ----------------- INPUTS -----------------
st.header("📥 Startup Inputs")

startup_name = st.text_input("Startup Name *")
sector = st.text_input("Sector")
stage = st.selectbox("Stage", ["Pre-Seed", "Seed"])
geography = st.text_input("Geography")

st.subheader("Startup Description *")
startup_description = st.text_area(
    "What does the company do and why do customers care?",
    height=120
)

st.subheader("Founder Information *")
founder_linkedin = st.text_input("Founder LinkedIn URL")
founder_background = st.text_area(
    "Paste LinkedIn About + Experience",
    height=120
)

st.subheader("Traction")
traction = st.text_area(
    "Users, revenue, pilots, LOIs (if any)",
    height=80
)

st.subheader("Business Model (IMPORTANT)")
business_model = st.text_area(
    "How does the company make money? Pricing, buyers, payers, assumptions.\n"
    "This helps the AI avoid guessing.",
    height=100
)

st.subheader("Go-To-Market Strategy (IMPORTANT)")
gtm_strategy = st.text_area(
    "Who is the buyer? How do they acquire customers? Sales motion?\n"
    "Pitch decks often miss this in extractable text.",
    height=100
)

st.subheader("Pitch Deck (Optional)")
pitch_deck = st.file_uploader(
    "Upload Pitch Deck (PDF, max 10MB)",
    type=["pdf"]
)

deck_text = ""
deck_warning = False

if pitch_deck:
    if pitch_deck.size > MAX_DECK_MB * 1024 * 1024:
        deck_warning = True
        st.warning(
            f"Pitch deck is {pitch_deck.size // (1024*1024)}MB. "
            f"Only decks under {MAX_DECK_MB}MB can be processed.\n\n"
            "The memo will rely on your written inputs instead."
        )
    else:
        deck_text = read_pdf(pitch_deck)

# ----------------- ANALYSIS -----------------
if st.button("🔍 Generate IC Memo"):

    if not startup_name or not startup_description or not founder_background:
        st.error("Startup name, description, and founder background are required.")
        st.stop()

    with st.spinner("Writing IC memo..."):

        PROMPT = f"""
CRITICAL CONSTRAINT:
You must ONLY use the information explicitly provided below.
Do NOT invent company names, products, traction, founders, numbers, or customers.
If information is missing, explicitly say "Information not provided."
If assumptions are made, clearly label them as assumptions.
Do NOT rename or substitute the company.
The company name is fixed and must be used consistently.

You are a venture capitalist writing an internal investment committee memo.
This memo is meant to persuade skeptical partners, not to summarize facts.

Writing style:
- First-person plural ("we believe", "we are concerned")
- Opinionated and honest
- Include conviction AND doubts
- No consultant or academic tone
- Narrative paragraphs, not bullets
- Explicitly call out uncomfortable or controversial aspects

Company Name: {startup_name}

Startup Details:
Sector: {sector}
Stage: {stage}
Geography: {geography}

Founder LinkedIn:
{founder_linkedin}

Founder Background:
{founder_background}

Startup Description:
{startup_description}

Traction:
{traction}

Business Model:
{business_model}

Go-To-Market Strategy:
{gtm_strategy}

Pitch Deck Extract (may be incomplete):
{deck_text}

Structure:
1. Investment Summary
2. Company & Product
3. Founder & Team
4. Traction & Early Signals
5. Market Opportunity
6. Business Model & Monetization
7. Risks & Concerns
8. Why This Can Win
9. Scoring (Market 35%, Founder 30%, Product 20%, Traction 10%, Risk 5%)
10. Key Open Questions
11. Final Recommendation (Proceed / Watch / Pass)

Formatting rules:
- No tables
- Clear section headers
- Normal numbers (e.g. "$5 million")
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=PROMPT
            )
            raw_output = response.text
        except Exception as e:
            st.error("AI request failed.")
            st.error(str(e))
            st.stop()

        output = clean_memo_text(raw_output)

        st.header("📄 Investment Memo")
        if deck_warning:
            st.info("⚠️ Pitch deck not fully processed — memo relies on written inputs.")

        st.markdown(output)

        # ----------------- EXPORT -----------------
        st.download_button(
            "⬇️ Download Memo (Markdown)",
            output,
            f"{startup_name}_investment_memo.md",
            "text/markdown"
        )

        pdf_safe_text = normalize_for_pdf(output)
        pdf = memo_to_pdf(pdf_safe_text)

        st.download_button(
            "⬇️ Download Memo (PDF)",
            pdf.output(dest="S").encode("latin-1"),
            f"{startup_name}_investment_memo.pdf",
            "application/pdf"
        )

        st.success("Memo generated successfully.")





