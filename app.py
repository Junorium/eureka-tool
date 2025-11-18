import streamlit as st
import pdfplumber
import pptx
import google.generativeai as genai
import pandas as pd
import json
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Eureka Pitch Scorer", layout="wide")

# --- 1. AUTHENTICATION ---
api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.error("🔑 API Key missing. Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()
genai.configure(api_key=api_key)

# --- 2. HELPER FUNCTIONS ---
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

def clean_json_response(response_text):
    """
    Sometimes the AI wraps JSON in markdown code blocks (```json ... ```).
    This function strips them out to get raw JSON.
    """
    # Remove code block markers
    text = re.sub(r'```json\n?', '', response_text)
    text = re.sub(r'```', '', text)
    return text.strip()

# --- 3. THE BRAIN ---
def analyze_pitch(deck_text):
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

    # WE REQUEST JSON OUTPUT NOW
    prompt = f"""
    You are a strict Judge for the 'Eureka' Pitch Competition.
    
    TASK: Score the uploaded pitch deck based *strictly* on the Eureka Rubric below.
    
    INPUT PITCH DECK:
    "{deck_text[:30000]}"

    RUBRIC:
    {rubric}

    OUTPUT FORMAT:
    You must respond with VALID JSON ONLY. Do not speak outside the JSON.
    The JSON must follow this exact structure:
    {{
        "reviews": [
            {{
                "category": "Problem Identification",
                "question": "1. What is the problem?",
                "score": 1,
                "reasoning": "The deck does not mention..."
            }},
            ... (one object for every question in rubric)
        ],
        "total_score": 0,
        "hard_truth": "A short, harsh summary paragraph."
    }}

    SCORING LEGEND:
    - 3 (High): Specific, evidence-based validation.
    - 2 (Medium): Present but vague.
    - 1 (Low): Missing or generic.
    """
    
    # Model Logic with Fallback
    model_options = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-pro"]
    
    for model_name in model_options:
        try:
            try:
                model = genai.GenerativeModel(model_name, generation_config={"response_mime_type": "application/json"})
            except:
                model = genai.GenerativeModel(f"models/{model_name}")
                
            response = model.generate_content(prompt)
            return response.text
        except Exception:
            continue
            
    return None

# --- 4. THE UI ---
st.title("Eureka Pitch Scorer")
st.markdown("### Drop in a deck. Get a structured scorecard.")

uploaded_file = st.file_uploader("Upload Pitch Deck", type=["pdf", "pptx"])

if uploaded_file and st.button("Run Evaluation"):
    with st.spinner("Reading file..."):
        ftype = uploaded_file.name.split(".")[-1].lower()
        extracted_text = extract_text(uploaded_file, ftype)
        
    if not extracted_text or len(extracted_text) < 50:
        st.error("Could not extract text.")
    else:
        with st.spinner("Judging (Thinking in JSON)..."):
            raw_result = analyze_pitch(extracted_text)
            
            if raw_result:
                try:
                    # Parse the JSON
                    data = json.loads(clean_json_response(raw_result))
                    
                    # 1. Display The "Hard Truth" First
                    st.error(f"The Hard Truth: {data.get('hard_truth', 'No summary provided.')}")
                    
                    # 2. Display Total Score
                    score = data.get('total_score', 0)
                    st.metric(label="Total Score (out of 36)", value=f"{score}/36")
                    
                    # 3. Display The Table
                    st.subheader("Detailed Rubric Breakdown")
                    
                    # Convert list of reviews to Pandas DataFrame for a pretty UI
                    df = pd.DataFrame(data['reviews'])
                    
                    # Configure the columns for the UI
                    st.dataframe(
                        df, 
                        column_config={
                            "score": st.column_config.NumberColumn(
                                "Score",
                                help="1 (Low) to 3 (High)",
                                format="%d ⭐"
                            ),
                            "reasoning": st.column_config.TextColumn(
                                "Judge's Reasoning",
                                width="large"
                            ),
                            "question": st.column_config.TextColumn(
                                "Rubric Question",
                                width="medium"
                            )
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                except json.JSONDecodeError:
                    st.error("The AI failed to produce valid JSON. Here is the raw text:")
                    st.text(raw_result)
            else:
                st.error("API Connection Failed.")
