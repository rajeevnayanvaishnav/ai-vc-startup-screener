import streamlit as st
import os
import re
from dotenv import load_dotenv
from pypdf import PdfReader
from google import genai
from fpdf import FPDF

# ----------------- SETUP -----------------
load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

st.set_page_config(page_title="AI VC Startup Screener", layout="wide")
st.title("🚀 AI Startup Screening & Investment Memo Generator")

# ----------------- HELPERS -----------------
def read_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return text[:8000]  # keep prompt safe on free tier


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

startup_name = st.text_input("Startup Name")
sector = st.text_input("Sector")
stage = st.selectbox("Stage", ["Pre-Seed", "Seed"])
geography = st.text_input("Geography")

st.subheader("Startup Description")
startup_description = st.text_area("Paste website copy / product description")

st.subheader("Founder Information")
founder_linkedin = st.text_input("Founder LinkedIn Profile URL")
founder_background = st.text_area(
    "Founder Background (LinkedIn About + Experience)"
)

st.subheader("Traction")
traction = st.text_area("Users, revenue, pilots, LOIs (if any)")

st.subheader("Pitch Deck (Optional)")
pitch_deck = st.file_uploader("Upload Pitch Deck (PDF)", type=["pdf"])
deck_text = read_pdf(pitch_deck) if pitch_deck else ""

# ----------------- ANALYSIS -----------------
if st.button("🔍 Analyze Startup"):

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

The company being evaluated is:
COMPANY NAME: {startup_name}

You are a venture capitalist writing an internal investment committee memo.
This memo is meant to persuade skeptical partners, not to summarize facts.

Writing style:
- Write in first-person plural ("we believe", "we are concerned")
- Be opinionated, thoughtful, and honest
- Include conviction AND doubts
- Avoid academic or consultant language
- Use narrative paragraphs
- Explicitly call out what makes this uncomfortable or controversial

Structure the memo as follows:

1. Investment Summary
2. Company & Product
3. Founder & Team
4. Traction & Early Signals
5. Market Opportunity
6. Business Model & Monetization
7. Risks & Concerns
8. Why This Can Win
9. Scoring (Early-Stage Weighted)
   - Market: 35%
   - Founder: 30%
   - Product: 20%
   - Traction: 10%
   - Risk: 5%
10. Key Open Questions
11. Final Recommendation (Proceed / Watch / Pass)

Startup Details:
Name: {startup_name}
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

Pitch Deck Notes:
{deck_text}

Formatting rules:
- Do NOT use tables
- Write currency normally (e.g. "$5 million")
- Use clear section headers
"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=PROMPT,
                config={"timeout": 60}
            )
            raw_output = response.text

        except Exception as e:
            st.error("AI request failed or timed out.")
            st.error(str(e))
            st.stop()

        output = clean_memo_text(raw_output)

        st.header("📄 Investment Memo")
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


