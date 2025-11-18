import streamlit as st
import pdfplumber
import pptx
import google.generativeai as genai
import json
import re
import urllib.parse

# --- CONFIGURATION ---
st.set_page_config(page_title="Eureka Pitch Scorer", layout="wide")

# --- 1. AUTHENTICATION ---
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("🔑 API Key missing. Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. KNOWLEDGE BASE (THE ANCHORS) ---
RUBRIC_GUIDE = """
CASE STUDY ANCHORS (Use these to grade):

1. PROBLEM IDENTIFICATION ("Why you?")
   ⭐ 1 STAR (BAD): "We are passionate students who love music." 
   (Reasoning: Generic passion, no unique leverage.)
   ⭐ 3 STAR (GOOD): "Our CTO holds a patent in audio signal processing and I managed a $2M inventory at Guitar Center."
   (Reasoning: Specific, verifiable, relevant domain expertise.)

2. CUSTOMER DISCOVERY ("Who is the customer?")
   ⭐ 1 STAR (BAD): "Everyone who owns a home is our customer."
   (Reasoning: TAM is not a customer profile. Too broad.)
   ⭐ 3 STAR (GOOD): "Our beachhead is single-family homeowners in the Northeast with oil heat (12% of region)."
   (Reasoning: Specific geography, demographic, and technical constraint.)

3. VALIDATION ("How do you know?")
   ⭐ 1 STAR (BAD): "We sent out a survey and people liked it."
   (Reasoning: Surveys are weak evidence of purchase intent.)
   ⭐ 3 STAR (GOOD): "We pre-sold 50 units at $20 each using a smoke-test landing page."
   (Reasoning: Financial commitment and actual behavior tracked.)
"""

RUBRIC_QUESTIONS = """
SECTION 1: PROBLEM
1. What is the problem you want to solve?
2. Why do you care about solving this problem?
3. Why are you uniquely qualified to solve this problem?
4. Initial thoughts on finding customers?
5. Initial thoughts on monetization?

SECTION 2: DISCOVERY
6. Who is the customer/end user?
7. Have you carved out user profile specifics? (Who have you talked to?)
8. How are customers currently solving this problem?
9. What are the competitive products?
10. Prototype status?
11. Analysis of results?
12. What do you need now?
"""

# --- 3. HELPER FUNCTIONS ---
def extract_text(file, file_type):
    text = ""
    try:
        if file_type == "pdf":
            with pdfplumber.open(file) as pdf:
                text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        elif file_type == "pptx":
            prs = pptx.Presentation(file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
    except Exception:
        return None
    return text

def clean_json_response(response_text):
    text = re.sub(r'```json\n?', '', response_text)
    text = re.sub(r'```', '', text)
    return text.strip()

def generate_google_link(query):
    encoded = urllib.parse.quote(query)
    return f"https://www.google.com/search?q={encoded}"

# --- 4. AGENT 1: THE JUDGE ---
def analyze_pitch(deck_text):
    prompt = f"""
    You are a strict Judge for the 'Eureka' Pitch Competition.
    
    TASK: Score the uploaded pitch deck based on the RUBRIC below.
    Use the "CASE STUDY ANCHORS" to determine if a score is 1 or 3.

    INPUT PITCH DECK:
    "{deck_text[:30000]}"

    RUBRIC QUESTIONS:
    {RUBRIC_QUESTIONS}

    CASE STUDY ANCHORS (STRICT RULES):
    {RUBRIC_GUIDE}

    OUTPUT FORMAT:
    Respond with VALID JSON ONLY:
    {{
        "reviews": [
            {{
                "question": "1. What is the problem?",
                "score": 1,
                "reasoning": "The deck only states..."
            }},
            ...
        ],
        "total_score": 0,
        "hard_truth": "Summary paragraph."
    }}
    """
    
    # Try models in order (Using your approved list)
    model_options = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    
    for m in model_options:
        try:
            model = genai.GenerativeModel(m, generation_config={"response_mime_type": "application/json"})
            return model.generate_content(prompt).text
        except:
            try:
                # Retry with 'models/' prefix if needed
                model = genai.GenerativeModel(f"models/{m}", generation_config={"response_mime_type": "application/json"})
                return model.generate_content(prompt).text
            except:
                continue
    return None

# --- 5. AGENT 2: THE TEACHER ---
def get_case_studies(weak_areas_list):
    weaknesses_str = "\n".join([f"- {w['question']} (Score: {w['score']})" for w in weak_areas_list])
    
    prompt = f"""
    You are a Startup Mentor. The user has failed the following areas in their pitch:
    {weaknesses_str}
    
    TASK:
    For EACH
