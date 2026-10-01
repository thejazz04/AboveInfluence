# =========================
# IMPORTS
# =========================
import streamlit as st
import pandas as pd
import json
from bs4 import BeautifulSoup
import ollama
import requests

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="YouTube Influence Intelligence",
    layout="wide",
)

WEBHOOK_URL = "https://va-run23.app.n8n.cloud/webhook/analyze-influence"

# =========================
# TITLE
# =========================
st.markdown(
    "<h1 style='text-align: center;'>🧠 Goal-Based YouTube Influence Intelligence</h1>",
    unsafe_allow_html=True
)

st.divider()

# =========================
# USER GOAL INPUT
# =========================

st.header("🎯 Define Your Future Goals")

g1, g2 = st.columns(2)

with g1:
    user_goal = st.text_input("What do you want to become?")
    focus_areas = st.text_area("Top 3 focus areas (e.g. Coding, Fitness, Finance)")
    daily_hours = st.slider("Daily hours available for growth", 1, 12, 4)

with g2:
    distraction_level = st.selectbox(
        "How easily are you distracted?",
        ["Low", "Moderate", "High"]
    )
    avoid_topics = st.text_area(
        "Topics you want to avoid (e.g. Politics, Drama, Clickbait)"
    )

st.divider()

# =========================
# FILE LOADERS
# =========================

def load_subscriptions(file):
    df = pd.read_csv(file)

    possible_cols = [col for col in df.columns if "name" in col.lower()]

    if possible_cols:
        df["channel_name"] = df[possible_cols[0]]
    elif len(df.columns) > 1:
        df["channel_name"] = df.iloc[:, 1]
    else:
        df["channel_name"] = df.iloc[:, 0]

    df["channel_name"] = df["channel_name"].astype(str).str.strip()

    return df[["channel_name"]]


def load_watch_history(file):
    soup = BeautifulSoup(file.read(), "lxml")
    records = []

    for div in soup.find_all("div"):
        links = div.find_all("a")
        if len(links) >= 2:
            records.append({
                "video_title": links[0].get_text(strip=True),
                "channel_name": links[1].get_text(strip=True).strip()
            })

    return pd.DataFrame(records)


# =========================
# CHANNEL ANALYSIS
# =========================

def analyze_channel_batch(batch_df):

    channel_lines = []
    for _, row in batch_df.iterrows():
        channel_lines.append(f"Channel: {row['channel_name']}")

    combined = "\n".join(channel_lines)

    prompt = f"""
You are a Personalized Influence Intelligence Engine.

User Goal:
{user_goal}

Focus Areas:
{focus_areas}

Daily Hours:
{daily_hours}

Distraction Level:
{distraction_level}

Topics To Avoid:
{avoid_topics}

For EACH channel return JSON list:

[
 {{
   "channel_name": "...",
   "primary_category": "...",
   "alignment_with_goal": "High/Medium/Low",
   "risk_level": "Low/Moderate/High (relative to user goal)",
   "influence_tactics": "...",
   "unsubscribe_recommendation": "...",
   "influence_score": 0-100
 }}
]

Channels:
{combined}
"""

    response = ollama.chat(
        model="phi3:mini",
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response["message"]["content"]

    start = raw.find("[")
    end = raw.rfind("]")

    if start != -1 and end != -1:
        try:
            parsed = json.loads(raw[start:end+1])
        except:
            parsed = []
    else:
        parsed = []

    return parsed


def analyze_all_channels(subs_df):

    batch_size = 6
    all_results = []

    for i in range(0, len(subs_df), batch_size):
        batch = subs_df.iloc[i:i+batch_size]
        batch_results = analyze_channel_batch(batch)
        all_results.extend(batch_results)

    return all_results


# =========================
# WATCHTIME ANALYSIS
# =========================

def generate_watchtime_summary(history_df):

    if history_df.empty:
        return {"total_watchtime_minutes": 0, "shorts_percentage": 0}

    history_df["watch_time"] = history_df.apply(
        lambda x: 1 if "short" in str(x).lower() else 8,
        axis=1
    )

    total_watchtime = history_df["watch_time"].sum()

    shorts_time = history_df[
        history_df.apply(lambda x: "short" in str(x).lower(), axis=1)
    ]["watch_time"].sum()

    shorts_percentage = 0
    if total_watchtime > 0:
        shorts_percentage = round(shorts_time / total_watchtime * 100, 2)

    return {
        "total_watchtime_minutes": int(total_watchtime),
        "shorts_percentage": shorts_percentage
    }


# =========================
# GOAL SUMMARY
# =========================

def generate_goal_summary(channel_data):

    prompt = f"""
User Goal:
{user_goal}

Focus Areas:
{focus_areas}

Daily Hours:
{daily_hours}

Channel Dataset:
{json.dumps(channel_data, indent=2)}

Generate:

1. Goal Alignment Score (0-100)
2. Top 5 channels helping goal
3. Top 5 channels harming goal
4. Risk Summary
5. Time Optimization Advice
6. Final Personalized Recommendation

Return structured text.
"""

    response = ollama.chat(
        model="phi3:mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response["message"]["content"]


# =========================
# LAYOUT
# =========================

left_col, center_col, right_col = st.columns([1, 2, 1])

with left_col:
    st.subheader("📂 Upload Data")
    subs_file = st.file_uploader("Upload Subscriptions CSV", type=["csv"])
    history_file = st.file_uploader("Upload Watch History HTML", type=["html"])

if subs_file and history_file and user_goal:

    with center_col:

        st.success("Files uploaded successfully!")

        subs_df = load_subscriptions(subs_file)
        history_df = load_watch_history(history_file)

        # ----------------------
        # Channel Analysis
        # ----------------------
        st.header("🔍 Personalized Channel Analysis")

        with st.spinner("Analyzing channels relative to your goals..."):
            channel_analysis = analyze_all_channels(subs_df)

        if not channel_analysis:
            st.error("AI failed to analyze channels.")
            st.stop()

        for ch in channel_analysis:
            with st.expander(
                f"{ch.get('channel_name','Unknown')} | Risk: {ch.get('risk_level','Unknown')}"
            ):
                st.write(f"**Primary Category:** {ch.get('primary_category','Unknown')}")
                st.write(f"**Alignment With Goal:** {ch.get('alignment_with_goal','Unknown')}")
                st.write(f"**Influence Tactics:** {ch.get('influence_tactics','Unknown')}")
                st.write(f"**Unsubscribe?** {ch.get('unsubscribe_recommendation','Unknown')}")
                st.write(f"**Influence Score:** {ch.get('influence_score','N/A')}")

        st.divider()

        # ----------------------
        # Watchtime
        # ----------------------
        st.header("⏱ Watchtime Summary")

        watch_summary = generate_watchtime_summary(history_df)

        st.metric("Total Watchtime (minutes)", watch_summary["total_watchtime_minutes"])
        st.metric("Shorts Consumption (%)", watch_summary["shorts_percentage"])

        st.divider()

        # ----------------------
        # Goal Alignment Summary
        # ----------------------
        st.header("📊 Goal Alignment Intelligence")

        with st.spinner("Generating personalized strategy..."):
            goal_report = generate_goal_summary(channel_analysis)

        st.markdown(goal_report)

        # ----------------------
        # n8n Trigger
        # ----------------------
        try:
            payload = {
                "goal": user_goal,
                "focus_areas": focus_areas,
                "channels": channel_analysis,
                "watchtime": watch_summary
            }
            requests.post(WEBHOOK_URL, json=payload)
            st.success("Sent to n8n workflow!")
        except:
            st.warning("n8n webhook not configured.")