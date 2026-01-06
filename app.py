import streamlit as st
import os
import re
from dotenv import load_dotenv
from pypdf import PdfReader
from google import genai
from fpdf import FPDF

# ----------------- SETUP -----------------
load_dotenv()

DEFAULT_API_KEY = os.getenv("GEMINI_API_KEY")

st.set_page_config(page_title="AI VC Startup Screener", layout="wide")
st.title("🚀 AI VC Startup Screening & Investment Memo Generator")

# ----------------- SIDEBAR (BYOK + MODE) -----------------
st.sidebar.header("⚙️ Settings")

memo_mode = st.sidebar.radio(
    "Memo Mode",
    ["Quick IC Memo", "Full IC Memo"],
    help="Quick mode is faster and uses fewer tokens."
)

user_api_key = st.sidebar.text_input(
    "Use your own Gemini API key (optional)",
    type="password",
    help="Your key is used only for this request and never stored."
)

effective_api_key = user_api_key if user_api_key else DEFAULT_API_KEY

if not effective_api_key:
    st.warning("No API key found. Add one in Streamlit Secrets or paste your own.")
    st.stop()

client = genai.Client(api_key=effective_api_key)

# ----------------- HELPERS -----------------
def read_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text[:3000]  # hard cap for token safety


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

startup_name = st.text_input("Startup Name")
sector = st.text_input("Sector")
stage = st.selectbox("Stage", ["Pre-Seed", "Seed"])
geography = st.text_input("Geography")

st.subheader("Startup Description")
startup_description = st.text_area("Paste website copy / product description")

st.subheader("Founder Information")
founder_linkedin = st.text_input("Founder LinkedIn Profile URL")
founder_background = st.text_area("Founder Background (LinkedIn About + Experience)")

st.subheader("Traction")
traction = st.text_area("Users, revenue, pilots, LOIs (if any)")

st.subheader("Pitch Deck (Optional)")
pitch_deck = st.file_uploader("Upload Pitch Deck (PDF)", type=["pdf"])
deck_text = read_pdf(pitch_deck) if pitch_deck else ""

deck_section = f"\nPitch Deck Notes:\n{deck_text}" if deck_text else ""

# ----------------- ANALYSIS -----------------
if st.button("🔍 Analyze Startup"):

    if not startup_name or not startup_description or not founder_background:
        st.error("Startup name, description, and founder background are required.")
        st.stop()

    with st.spinner("Writing IC memo..."):

        if memo_mode == "Quick IC Memo":
            PROMPT = f"""
CRITICAL CONSTRAINT:
Use ONLY the information explicitly provided.
Do NOT invent facts. If missing, say "Information not provided."

Company: {startup_name}

Write a SHORT internal VC memo (max 500 words).

Cover:
1. What the company does
2. Why this could matter
3. Founder assessment
4. Market snapshot
5. Top 3 risks
6. Preliminary recommendation (Proceed / Watch / Pass)

Be opinionated, concise, and honest.

Startup Description:
{startup_description}

Founder Background:
{founder_background}

Traction:
{traction}
"""
        else:
            PROMPT = f"""
CRITICAL CONSTRAINT:
You must ONLY use the information explicitly provided below.
Do NOT invent company names, products, traction, founders, numbers, or customers.
If information is missing, explicitly say "Information not provided."
If assumptions are made, clearly label them as assumptions.
Do NOT rename or substitute the company.

Company name: {startup_name}

Write an internal VC investment committee memo.

Startup details:
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
{deck_section}

Sections:
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
- Clean paragraphs
- Normal numbers (e.g. "$5 million")
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=PROMPT
            )
            raw_output = response.text

        except Exception as e:
            if "RESOURCE_EXHAUSTED" in str(e):
                st.warning(
                    "⚠️ AI quota exhausted.\n\n"
                    "Please wait a minute, switch to Quick IC Memo, "
                    "or use your own API key."
                )
            else:
                st.error("AI request failed.")
                st.error(str(e))
            st.stop()

        output = clean_memo_text(raw_output)

        st.header("📄 Investment Memo")
        st.markdown(output)

        st.download_button(
            "⬇️ Download Memo (Markdown)",
            output,
            f"{startup_name}_investment_memo.md",
            "text/markdown"
        )

        pdf_safe = normalize_for_pdf(output)
        pdf = memo_to_pdf(pdf_safe)

        st.download_button(
            "⬇️ Download Memo (PDF)",
            pdf.output(dest="S").encode("latin-1"),
            f"{startup_name}_investment_memo.pdf",
            "application/pdf"
        )

        st.success("Memo generated successfully.")



