import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- CONFIGURATION ---
API_KEY = '63ba1313af494222bddfb7f14879b920' 
BASE_URL = "https://api.football-data.org/v4/competitions/WC/standings"

# --- DATA: OFFICIAL 2026 GROUPS ---
groups = {
    "Group A": ["Mexico", "South Africa", "South Korea", "Czechia"],
    "Group B": ["Canada", "Switzerland", "Qatar", "Bosnia"],
    "Group C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "Group D": ["USA", "Paraguay", "Australia", "Türkiye"],
    "Group E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "Group F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "Group G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "Group H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "Group I": ["France", "Senegal", "Norway", "Iraq"],
    "Group J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "Group K": ["Portugal", "Uzbekistan", "Colombia", "DR Congo"],
    "Group L": ["England", "Croatia", "Ghana", "Panama"]
}

# --- GOOGLE SHEETS CONNECTION ---
def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # Accessing secrets from the TOML configuration
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("World_Cup_Pool_Data").sheet1

# --- API DATA FETCHING ---
@st.cache_data(ttl=3600) 
def get_official_advancers():
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{BASE_URL}?season=2026", headers=headers)
        data = response.json()
        advancers = []
        thirds = []
        if 'standings' in data:
            for group in data['standings']:
                table = group['table']
                if len(table) >= 2:
                    advancers.extend([table[0]['team']['name'], table[1]['team']['name']])
                if len(table) >= 3:
                    thirds.append({'name': table[2]['team']['name'], 'pts': table[2]['points'], 'gd': table[2]['goalDifference']})
            # Best 8 third-place teams advance in the 48-team format
            thirds.sort(key=lambda x: (x['pts'], x['gd']), reverse=True)
            advancers.extend([t['name'] for t in thirds[:8]])
        return advancers
    except Exception:
        return []

# --- APP UI SETUP ---
st.set_page_config(page_title="2026 World Cup Pool", layout="wide")

# Sidebar Navigation
st.sidebar.title("Tournament Menu")
page = st.sidebar.radio("Go to:", ["Make Predictions", "Leaderboard", "Rules"])

# User Info Sidebar
with st.sidebar:
    st.divider()
    user_name = st.text_input("Enter Your Full Name:")

# --- PAGE 1: PREDICTIONS ---
if page == "Make Predictions":
    st.title("🏆 2026 World Cup Group Stage Predictions")
    st.markdown("Rank the teams in each group from **1st to 4th**. Your top 3 picks will earn you points if they advance.")
    
    all_picks = []
    cols = st.columns(3) 
    
    for i, (group_name, teams) in enumerate(groups.items()):
        with cols[i % 3]:
            st.subheader(group_name)
            p1 = st.selectbox("1st Place", ["--"] + teams, key=f"{group_name}_1")
            rem2 = [t for t in teams if t != p1]
            p2 = st.selectbox("2nd Place", ["--"] + rem2, key=f"{group_name}_2")
            rem3 = [t for t in rem2 if t != p2]
            p3 = st.selectbox("3rd Place", ["--"] + rem3, key=f"{group_name}_3")
            rem4 = [t for t in rem3 if t != p3]
            p4 = st.selectbox("4th Place", ["--"] + rem4, key=f"{group_name}_4")
            all_picks.extend([p1, p2, p3, p4])

    if st.button("Submit My Picks", use_container_width=True):
        if not user_name:
            st.error("Please enter your name in the sidebar.")
        elif "--" in all_picks:
            st.error("Please complete all rankings for every group.")
        else:
            try:
                sheet = connect_to_sheet()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sheet.append_row([timestamp, user_name] + all_picks + ["Pending"])
                st.success("Your predictions have been saved successfully!")
                st.balloons()
            except Exception as e:
                st.error("Error connecting to Google Sheets. Verify your Secrets configuration.")

# --- PAGE 2: LEADERBOARD ---
elif page == "Leaderboard":
    st.title("📊 Tournament Leaderboard")
    with st.spinner("Fetching live results..."):
        official_list = get_official_advancers()
        try:
            sheet = connect_to_sheet()
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                
                def calculate_score(row):
                    points = 0
                    row_list = list(row.values())
                    # Data starts at index 2 (after Timestamp and Name)
                    # Groups are in chunks of 4; we score the top 3 of each chunk
                    for g_idx in range(12):
                        start_col = 2 + (g_idx * 4)
                        for rank_offset in range(3): 
                            pick = row_list[start_col + rank_offset]
                            if pick in official_list:
                                points += 1
                    return points
                
                df['Score'] = df.apply(calculate_score, axis=1)
                leaderboard = df[['Name', 'Score', 'Status']].sort_values(by='Score', ascending=False)
                st.table(leaderboard)
            else:
                st.info("No submissions found yet.")
        except Exception:
            st.error("Could not load the leaderboard.")

# --- PAGE 3: RULES ---
elif page == "Rules":
    st.title("📜 Rules and Information")
    
    st.subheader("Entry Details")
    st.write("- **Fee:** $10 USD / $15 CAD / £7.50 GBP")
    st.write("- **Deadline:** Picks must be submitted before the first match of the tournament kicks off.")
    
    st.subheader("Scoring System")
    st.info("You earn **1 Point** for every team in your predicted **Top 3** of a group that officially advances to the Round of 32.")
    
    st.subheader("Payment Info")
    st.markdown("""
    - **Venmo (USA):** @jhradecky
    - **E-transfer (Canada):** julien.hradecky@gmail.com
    """)
    
    st.subheader("Prize Breakdown")
    st.write("1. **1st Place:** 70% of the pot")
    st.write("2. **2nd Place:** 20% of the pot")
    st.write("3. **3rd Place:** Entry fee refund")
