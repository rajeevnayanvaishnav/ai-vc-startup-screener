import streamlit as st
import os
import re
import requests
from dotenv import load_dotenv
from pypdf import PdfReader
from fpdf import FPDF

# ----------------- SETUP -----------------
load_dotenv()

DEFAULT_OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")

st.set_page_config(page_title="AI VC Startup Screener", layout="wide")
st.markdown(
    """
    <style>
    .memo-container {
        max-width: 900px;
        margin: auto;
        font-size: 16px;
        line-height: 1.65;
        color: #e6e6e6;
    }

    .memo-container h1 {
        font-size: 24px;
        margin-top: 32px;
        margin-bottom: 12px;
    }

    .memo-container h2 {
        font-size: 20px;
        margin-top: 28px;
        margin-bottom: 10px;
    }

    .memo-container h3 {
        font-size: 18px;
        margin-top: 24px;
        margin-bottom: 8px;
    }

    .memo-container p {
        margin-bottom: 14px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🚀 AI VC Startup Screening & Investment Memo Generator")

# ----------------- SIDEBAR -----------------
st.sidebar.header("⚙️ Settings")

memo_mode = st.sidebar.radio(
    "Memo Mode",
    ["Quick IC Memo", "Full IC Memo"],
    help="Quick mode is faster and uses fewer tokens."
)

user_api_key = st.sidebar.text_input(
    "Use your own OpenRouter API key (optional)",
    type="password",
    help="Used only for this request. Never stored."
)

OPENROUTER_KEY = user_api_key if user_api_key else DEFAULT_OPENROUTER_KEY

if not OPENROUTER_KEY:
    st.warning("No OpenRouter API key found. Add one in Secrets or paste your own.")
    st.stop()

# ----------------- HELPERS -----------------
def read_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text[:3000]  # hard cap for safety


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


def call_nex_agi(prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "AI VC Startup Screener",
    }

    payload = {
        "model": "nex-agi/deepseek-v3.1-nex-n1:free",
        "messages": [
            {"role": "system", "content": "You are a venture capitalist writing internal IC memos."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 2000
    }

    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

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
            raw_output = call_nex_agi(PROMPT)
        except Exception as e:
            st.error("AI request failed.")
            st.error(str(e))
            st.stop()

        output = clean_memo_text(raw_output)

        st.header("📄 Investment Memo")
        st.markdown(
        f"<div class='memo-container'>{output}</div>",
        unsafe_allow_html=True
        )



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




