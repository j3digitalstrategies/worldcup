import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import io

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
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Ensure this matches your Google Sheet name exactly
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
            thirds.sort(key=lambda x: (x['pts'], x['gd']), reverse=True)
            advancers.extend([t['name'] for t in thirds[:8]])
        return advancers
    except:
        return []

# --- APP UI SETUP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation", ["Make Predictions", "Leaderboard", "Rules"])

with st.sidebar:
    st.header("Player Info")
    user_name = st.text_input("Full Name:")

# --- PAGE 1: PREDICTIONS ---
if page == "Make Predictions":
    st.title("🏆 2026 World Cup Predictions")
    st.info("Rank teams 1-4. Your top 3 picks are used for scoring.")
    
    all_picks = []
    summary_data = [] 
    cols = st.columns(4) 
    for i, (group_name, teams) in enumerate(groups.items()):
        with cols[i % 4]:
            st.markdown(f"### {group_name}")
            r1 = st.selectbox("1st", ["--"] + teams, key=f"{group_name}_1")
            rem2 = [t for t in teams if t != r1]
            r2 = st.selectbox("2nd", ["--"] + rem2, key=f"{group_name}_2")
            rem3 = [t for t in rem2 if t != r2]
            r3 = st.selectbox("3rd", ["--"] + rem3, key=f"{group_name}_3")
            rem4 = [t for t in rem3 if t != r3]
            r4 = st.selectbox("4th", ["--"] + rem4, key=f"{group_name}_4")
            
            all_picks.extend([r1, r2, r3, r4])
            summary_data.append({"Group": group_name, "1st": r1, "2nd": r2, "3rd": r3, "4th": r4})

    if st.button("Submit Rankings", use_container_width=True):
        if not user_name:
            st.error("Enter your name in the sidebar.")
        elif "--" in all_picks:
            st.error("Complete all rankings.")
        else:
            try:
                sheet = connect_to_sheet()
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                # Append row: [Timestamp, Name, GroupA1, GroupA2... Status]
                sheet.append_row([timestamp, user_name] + all_picks + ["Pending"])
                st.success("Predictions Saved!")
                
                # RESTORED: Download Section
                st.markdown("### 📥 Save Your Picks")
                df_user = pd.DataFrame(summary_data)
                csv = df_user.to_csv(index=False).encode('utf-8')
                
                st.download_button(
                    label="Download My Picks (.csv)",
                    data=csv,
                    file_name=f"{user_name}_WC2026_Picks.csv",
                    mime="text/csv",
                )
                st.balloons()
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")

# --- PAGE 2: LEADERBOARD ---
elif page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    with st.spinner("Calculating live scores..."):
        official_list = get_official_advancers()
        try:
            sheet = connect_to_sheet()
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                
                def run_scoring(row):
                    score = 0
                    # Convert row to list to access by index
                    # Index 0: Timestamp, Index 1: Name, Index 2+: Picks
                    row_vals = list(row.values())
                    for g_idx in range(12):
                        start = 2 + (g_idx * 4)
                        for i in range(3): # Score only top 3 picks per group
                            try:
                                if row_vals[start + i] in official_list:
                                    score += 1
                            except IndexError:
                                continue
                    return score
                
                df['Points'] = df.apply(run_scoring, axis=1)
                # Ensure 'Status' column exists in your sheet for this to work
                final_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
                st.table(final_df)
            else:
                st.info("No entries yet.")
        except Exception as e:
            st.error(f"Leaderboard Error: {e}")

# --- PAGE 3: RULES ---
elif page == "Rules":
    st.title("📜 Pool Rules & Payment")
    st.warning("⚠️ **Deadline:** All picks for the first round must be submitted before kickoff of the first match.")
    
    st.subheader("💰 Entry Fee")
    st.write("* **$10 USD / $15 CAD / £7.50 GBP**")
    
    st.subheader("💳 How to Pay")
    st.info("**USA:** Venmo @jhradecky  \n**Canada:** E-transfer julien.hradecky@gmail.com")
    
    st.subheader("🏆 Prizes")
    st.write("* **1st Place:** 70% of the total pot")
    st.write("* **2nd Place:** 20% of the total pot")
    st.write("* **3rd Place:** Entry fee refund")

    st.subheader("⚽ Scoring Logic")
    st.markdown("""
    * **1 Point** for every team in your **Top 3** that advances to the Round of 32.
    * Scores are updated automatically via live tournament data.
    * Participants must be marked as **'Paid'** in the 'Status' column of the sheet to be eligible.
    """)
