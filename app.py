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

# --- 2. KNOWLEDGE BASE (THE RIGOROUS RUBRIC) ---
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
[3] "We conducted 50 'Mom Test' interviews and have 5
