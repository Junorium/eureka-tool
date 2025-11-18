import streamlit as st
import pdfplumber
import pptx
import google.generativeai as genai
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="Eureka Pitch Scorer", layout="wide")

# --- 1. AUTHENTICATION (Loads from Secrets) ---
# We check if the key is in Streamlit Secrets (for Cloud) or local environment
api_key = st.secrets.get("GEMINI_API_KEY")

if not api_key:
    st.error("🔑 API Key missing. Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. PARSING FUNCTIONS ---
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
    except Exception as e:
        return None
    return text

# --- 3. THE BRAIN (Eureka Rubric Logic) ---
def analyze_pitch(deck_text):
    # The Eureka Rubric explicitly defined
    rubric = """
    SECTION 1: PROBLEM IDENTIFICATION
    1. What is the problem you want to solve?
    2. Why do you care about solving this problem?
    3. Why are you uniquely qualified to solve this problem?
    4. What are your initial thoughts on how to find/identify your customers?
    5. What are your initial thoughts on how you will monetize your idea?

    SECTION 2: CUSTOMER DISCOVERY
    6. Who is the customer and/or end user that has this problem?
    7. Have you carved out the user profile specifics? How do you know? Who have you talked to?
    8. How are your customers currently solving this problem?
    9. What are the competitive products in the market?
    10. What have you done to prototype your ideas?
    11. How have you responded or analyzed your results?
    12. What do you need now?
    """

    prompt = f"""
    You are a strict Judge for the 'Eureka' Pitch Competition.
    
    TASK: Score the uploaded pitch deck based *strictly* on the Eureka Rubric below.
    
    SCORING LEGEND:
    - **3 (High):** Specific, evidence-based, clearly defined (e.g., cites specific interviews, numbers, or distinct validation).
    - **2 (Medium):** Present but vague (e.g., "People need this" without proof).
    - **1 (Low):** Missing, completely generic, or ignored.

    INPUT PITCH DECK:
    "{deck_text[:15000]}"

    RUBRIC QUESTIONS:
    {rubric}

    OUTPUT INSTRUCTIONS:
    Generate a Markdown table with exactly these columns:
    | Category | Question | Score (1-3) | Judge's Reasoning (Cite specific text) |

    After the table, provide:
    1. **Total Score** (Calculated sum out of 36).
    2. **The "Hard Truth"**: One paragraph on why this pitch would fail investment today.
    """
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text

# --- 4. THE USER INTERFACE ---
st.title("💡 Eureka Pitch Scorer")
st.markdown("""
**Instructions for Advisor:**
1. Drop the student's **PPTX** or **PDF** below.
2. Wait ~10 seconds.
3. Get a strict **1-3 score** based exactly on the Eureka Rubric questions.
""")

uploaded_file = st.file_uploader("Upload Pitch Deck", type=["pdf", "pptx"])

if uploaded_file:
    if st.button("Run Evaluation"):
        with st.spinner("Reading file and consulting the rubric..."):
            # Determine file type
            ftype = uploaded_file.name.split(".")[-1].lower()
            
            # Extract
            extracted_text = extract_text(uploaded_file, ftype)
            
            if not extracted_text or len(extracted_text) < 50:
                st.error("⚠️ Could not read text. Ensure the PDF/PPTX is text-based, not just images.")
            else:
                # Analyze
                result = analyze_pitch(extracted_text)
                st.success("Evaluation Complete")
                st.markdown("### 📋 Scorecard")
                st.markdown(result)