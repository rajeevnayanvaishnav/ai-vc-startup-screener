import streamlit as st
import os
import re
from dotenv import load_dotenv
from pypdf import PdfReader
import google.generativeai as genai
from fpdf import FPDF

# ----------------- SETUP -----------------
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("models/gemini-flash-latest")

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
    return text[:10000]  # stay within free-tier limits

def clean_memo_text(text: str) -> str:
    # Fix broken spacing between letters/numbers
    text = re.sub(r'(?<=\w)\s+(?=\w)', ' ', text)
    text = re.sub(r'(\d)\s+([a-zA-Z])', r'\1\2', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def memo_to_pdf(text):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    for line in text.split("\n"):
        pdf.multi_cell(0, 6, line)
    return pdf

def normalize_for_pdf(text: str) -> str:
    replacements = {
        "—": "-",   # em dash
        "–": "-",   # en dash
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


# ----------------- INPUTS -----------------
st.header("📥 Startup Inputs")

startup_name = st.text_input("Startup Name")
sector = st.text_input("Sector")
stage = st.selectbox("Stage", ["Pre-Seed", "Seed"])
geography = st.text_input("Geography")

st.subheader("Startup Description")
startup_description = st.text_area(
    "Paste website copy / product description"
)

st.subheader("Founder Information")
founder_linkedin = st.text_input("Founder LinkedIn Profile URL")
founder_background = st.text_area(
    "Founder Background (LinkedIn About + Experience)"
)

st.subheader("Traction ")
traction = st.text_area(
    "Users, revenue, pilots, LOIs (if any)"
)

st.subheader("Pitch Deck")
pitch_deck = st.file_uploader("Upload Pitch Deck (PDF)", type=["pdf"])
deck_text = read_pdf(pitch_deck) if pitch_deck else ""

# ----------------- ANALYSIS -----------------
if st.button("🔍 Analyze Startup"):

    if not startup_name or not startup_description or not founder_background:
        st.error("Startup name, description, and founder background are required.")
    else:
        with st.spinner("Writing IC memo..."):

            BASE_PROMPT = f"""
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
- Use narrative paragraphs, not just bullet points
- Explicitly call out what makes this uncomfortable or controversial

Structure the memo as follows:

1. Investment Summary
State the proposed investment, stage, and why this company is worth discussing now.

2. Company & Product
Explain what the company does in simple terms and why customers care.
Focus on insight, not features.

3. Founder & Team
Discuss founder–problem fit, strengths, gaps, and whether this team can scale.
If there are weaknesses, state them clearly.

4. Traction & Early Signals
Describe what traction exists and why it matters (or why it may be misleading).
If traction is limited, explain what gives confidence anyway.

5. Market Opportunity
Frame the market using comparable companies, historical analogies, or category shifts.
Avoid fake precision.

6. Business Model & Monetization
Explain how money could be made and what is still unproven.

7. Risks & Concerns
List the top 3–5 risks that could kill this investment.
Do not soften them.

8. Why This Can Win
Explain what would have to go right for this to be a breakout company.

9. Scoring (Early-Stage Weighted)
Score each category from 0–10 with brief justification.

- Market: 35%
- Founder: 30%
- Product: 20%
- Traction: 10%
- Risk: 5%

Scoring guidance:
- 9–10: Rare, exceptional
- 7–8: Strong but with clear risks
- 5–6: Average / unclear
- <5: Weak signal

Calculate a weighted composite score out of 10.

10. Key Open Questions
List 3–5 critical unanswered questions that must be resolved before proceeding.

11. Final Recommendation
End with a clear recommendation: Proceed / Watch / Pass
Include a concise IC-style rationale.

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
- Do NOT use tables.
- Write currency and numbers normally (e.g. "$5 million", "25%").
- Use clean paragraphs and clear section headers only.
"""

            response = model.generate_content(BASE_PROMPT)
            raw_output = response.text
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

