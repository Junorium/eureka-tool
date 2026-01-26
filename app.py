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
    st.error("API Key missing. Please add GEMINI_API_KEY to Streamlit Secrets.")
    st.stop()

genai.configure(api_key=api_key)

# --- 2. KNOWLEDGE BASE (THE ANCHORS) ---
RUBRIC_GUIDE = """
SCORING PHILOSOPHY:
- 1 STAR (WEAK): Generic, vague, assumes "everyone" is a customer, lacks data, purely aspirational.
- 2 STAR (AVERAGE): Plausible logic, standard execution, broad but defined market, secondary research used.
- 3 STAR (STRONG): "Hair on fire" problem, hyper-specific beachhead, primary data (interviews/sales), unfair advantage (IP/unique history).

--- DETAILED CRITERIA MATRIX ---

Q1: THE PROBLEM
[1] "People are bored" or "It's hard to find X." (Subjective, low pain).
[2] "Small businesses spend too much time on accounting." (Plausible pain, but generalized).
[3] "Dentists lose $15k/year because insurance claim form 14B is manual." (Quantified, financial, acute pain).

Q2: WHY CARE?
[1] "We are passionate about this." (Subjective emotion).
[2] "The market is growing by 10% YOY." (Macro trend, but not urgent).
[3] "New federal regulation requires this change by 2025 or fines occur." (Urgency/Inevitability).

Q3: TEAM QUALIFICATIONS
[1] "We are hard-working students/friends." (Generic effort).
[2] "We are CS majors and one of us studies finance." (Relevant skills, but no track record).
[3] "CTO has a patent in this specific tech; CEO sold a similar SaaS for $5M." (Unfair advantage/proven execution).

Q4: FINDING CUSTOMERS (GTM)
[1] "Social media ads and SEO." (The generic "spray and pray").
[2] "We will partner with University clubs and use instagram influencers." (Targeted, but standard).
[3] "Direct sales to the top 50 distributors in the Northeast; LOI signed with 2 already." (Specific channel strategy with traction).

Q5: MONETIZATION
[1] "We will sell data" or "Ads." (Lazy monetization).
[2] "Subscription model ($10/month)." (Standard, logical).
[3] "Tiered SaaS: Freemium entry, $500/mo enterprise tier. LTV/CAC ratio modeled at 3:1." ( sophisticated unit economics).

Q6: THE CUSTOMER (BEACHHEAD)
[1] "Everyone with a smartphone." (Too broad).
[2] "College students in the US." (Segmented, but still massive).
[3] "Sophomore Medical Students struggling with Biochemistry in the Ivy League." (Hyper-segmented beachhead).

Q7: USER PROFILES (INTERVIEWS)
[1] "We sent a survey to our friends." (Biased, low effort).
[2] "We interviewed 20 people in the target demographic." (Good effort, qualitative).
[3] "We conducted 50 'Mom Test' interviews and have 5 signed Letters of Intent." (Rigorous discovery + commitment).

Q8: CURRENT SOLUTIONS (STATUS QUO)
[1] "Nothing exists like this." (Naive/False).
[2] "They use Excel or Pen & Paper." (Accurate observation).
[3] "They hire a temp agency for $40/hr which has a 20% error rate." (Deep understanding of the alternative's cost).

Q9: COMPETITION
[1] "We have no competitors." (Red flag).
[2] "Competitor X is expensive, we are cheaper." (Price war is a weak moat).
[3] "Competitor X is legacy on-premise software; we are cloud-native and 10x faster to deploy." (Structural/Technical advantage).

Q10: PROTOTYPE STATUS
[1] "Idea phase / Sketches."
[2] "Figma Mockups / Clickable frontend."
[3] "Functional MVP in the hands of 10 beta testers."

Q11: TRACTION/RESULTS
[1] "People said they would buy it." (Talk is cheap).
[2] "Waitlist of 100 emails." (Interest, but no skin in the game).
[3] "$2,000 in pre-sales or 50 active daily users." (Irrefutable proof of value).

Q12: THE ASK
[1] "We need money to build it." (Vague).
[2] "We need $50k for development and marketing." (Standard).
[3] "We need $50k to hire 1 engineer to reach 1,000 users, allowing us to raise Seed round." (Milestone-based funding).
"""

RUBRIC_QUESTIONS = """
SECTION 1: PROBLEM & TEAM
1. What is the specific problem you want to solve?
2. Why is this problem urgent or important (Why care)?
3. Why is this team uniquely qualified to solve it?
4. What is the Go-To-Market strategy (Finding customers)?
5. How does the business make money (Monetization)?

SECTION 2: DISCOVERY & VALIDATION
6. Who is the specific beachhead customer?
7. Validated User Profile (Who have you actually interviewed)?
8. Status Quo: How are customers solving this today?
9. Competition: Why will you win against incumbents?
10. Prototype/Product Status?
11. Traction/Analysis of Results?
12. The Ask: What do you need specifically?
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
    You are a Venture Capital Associate judging the 'Eureka' Pitch Competition.
    Your goal is to provide a harsh but fair assessment using a strict 3-point scale.
    
    CRITICAL INSTRUCTION: You must distinguish between "Average" (2) and "Great" (3). 
    Do not default to 1. If they show logic but no data, give them a 2. If they show data/traction, give them a 3.

    INPUT PITCH DECK TEXT:
    "{deck_text[:30000]}"

    GRADING MATRIX (Use this strictly):
    {RUBRIC_GUIDE}

    QUESTIONS TO SCORE:
    {RUBRIC_QUESTIONS}

    OUTPUT FORMAT (JSON ONLY):
    {{
        "reviews": [
            {{
                "question": "1. What is the specific problem?",
                "score": 2,
                "reasoning": "You identified a plausible pain point regarding X, but you did not quantify the financial loss, keeping this from a 3."
            }},
             ... (Repeat for all 12 questions)
        ],
        "total_score": 0,
        "hard_truth": "A 2-3 sentence summary of why they would or would not get funding right now."
    }}
    """
    
    # Try models in order
    model_options = ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    
    for m in model_options:
        try:
            model = genai.GenerativeModel(m, generation_config={"response_mime_type": "application/json"})
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
    For EACH weakness, identify a famous successful startup (Airbnb, Dropbox, Uber, DoorDash, etc.) that solved this specific problem perfectly in their early pitch deck.
    
    OUTPUT FORMAT (JSON):
    {{
        "case_studies": [
            {{
                "weakness": "Customer Discovery",
                "example_company": "Airbnb",
                "lesson": "Airbnb didn't just say 'travelers'. They specifically targeted attendees of a design conference in SF when hotels were sold out.",
                "search_query": "Airbnb pitch deck customer validation slide" 
            }}
        ]
    }}
    """
    
    # FIXED: Loop through approved models
    model_options = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]
    
    for m in model_options:
        try:
            model = genai.GenerativeModel(m, generation_config={"response_mime_type": "application/json"})
            return model.generate_content(prompt).text
        except:
             try:
                model = genai.GenerativeModel(f"models/{m}", generation_config={"response_mime_type": "application/json"})
                return model.generate_content(prompt).text
             except:
                continue
    return None

# --- 6. THE UI ---
st.title("EUREKA! Pitch Scorer & Coach")

if "analysis_data" not in st.session_state:
    st.session_state["analysis_data"] = None

uploaded_file = st.file_uploader("Upload Pitch Deck", type=["pdf", "pptx"])

if uploaded_file and st.button("Run Evaluation"):
    with st.spinner("Reading file..."):
        ftype = uploaded_file.name.split(".")[-1].lower()
        extracted_text = extract_text(uploaded_file, ftype)
        
    if extracted_text:
        with st.spinner("Judging..."):
            raw_result = analyze_pitch(extracted_text)
            if raw_result:
                try:
                    st.session_state["analysis_data"] = json.loads(clean_json_response(raw_result))
                except:
                    st.error("Error parsing AI response. Please try again.")

# --- DISPLAY RESULTS ---
if st.session_state["analysis_data"]:
    data = st.session_state["analysis_data"]
    
    # Top Section: Score
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Total Score", f"{data.get('total_score')}/36")
    with col2:
        st.error(f"**The Hard Truth:** {data.get('hard_truth')}")

    st.divider()
    st.subheader("Detailed Report Card")
    
    # Report Card Loop
    if 'reviews' in data:
        for review in data['reviews']:
            score = review['score']
            color = "red" if score == 1 else "orange" if score == 2 else "green"
            
            # THIS was the problematic line in your previous file.
            # We use st.columns([1, 4]) to define widths.
            with st.container():
                c1, c2 = st.columns([1, 4])
                with c1:
                    st.markdown(f"**{review['question']}**")
                    st.markdown(f":{color}[**Score: {score}/3**]")
                with c2:
                    st.markdown(f"_{review['reasoning']}_")
                st.divider()

    # --- REMEDIATION SECTION ---
    weak_points = [r for r in data.get('reviews', []) if r['score'] < 3]
    
    if weak_points:
        st.header("Case Study Remediation")
        st.info(f"We found {len(weak_points)} areas for improvement. Click below to see how unicorn companies solved these specific problems.")
        
        if st.button("Find Case Studies for My Weaknesses"):
            with st.spinner("Searching for similar business cases..."):
                remedy_raw = get_case_studies(weak_points)
                
                if remedy_raw:
                    try:
                        remedy_data = json.loads(clean_json_response(remedy_raw))
                        
                        for study in remedy_data.get('case_studies', []):
                            with st.expander(f"Fixing: {study['weakness']} (Example: {study['example_company']})", expanded=True):
                                st.markdown(f"**The Lesson:** {study['lesson']}")
                                link = generate_google_link(study['search_query'])
                                st.markdown(f"**[Click to see the real slide on Google]({link})**")
                                st.caption(f"Search Query: '{study['search_query']}'")
                                
                    except Exception as e:
                        st.error(f"Could not load case studies. Error: {e}")
                else:
                    st.error("Could not connect to AI models for case studies.")
