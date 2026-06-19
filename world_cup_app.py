import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

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

INITIAL_SEED_STANDINGS = {
    "Group A": ["Mexico", "South Korea", "Czechia", "South Africa"],
    "Group B": ["Switzerland", "Canada", "Qatar", "Bosnia"],
    "Group C": ["Scotland", "Morocco", "Brazil", "Haiti"],
    "Group D": ["USA", "Australia", "Türkiye", "Paraguay"],
    "Group E": ["Germany", "Ivory Coast", "Ecuador", "Curaçao"],
    "Group F": ["Sweden", "Japan", "Netherlands", "Tunisia"],
    "Group G": ["New Zealand", "Iran", "Belgium", "Egypt"],
    "Group H": ["Uruguay", "Saudi Arabia", "Spain", "Cape Verde"],
    "Group I": ["Norway", "France", "Senegal", "Iraq"],
    "Group J": ["Argentina", "Austria", "Jordan", "Algeria"],
    "Group K": ["DR Congo", "Portugal", "Colombia", "Uzbekistan"],
    "Group L": ["England", "Ghana", "Panama", "Croatia"]
}

CLEAN_TEAM_MAP = {
    "mexico": "Mexico", "southafrica": "South Africa", "southkorea": "South Korea",
    "korearepublic": "South Korea", "republicofkorea": "South Korea", "czechia": "Czechia", 
    "czechrepublic": "Czechia", "canada": "Canada", "switzerland": "Switzerland", "qatar": "Qatar",
    "bosnia": "Bosnia", "bosniaandherzegovina": "Bosnia", "bosniaherzegovina": "Bosnia",
    "brazil": "Brazil", "morocco": "Morocco", "haiti": "Haiti",
    "scotland": "Scotland", "usa": "USA", "unitedstates": "USA", "paraguay": "Paraguay",
    "australia": "Australia", "türkiye": "Türkiye", "turkey": "Türkiye",
    "germany": "Germany", "curaçao": "Curaçao", "curacao": "Curaçao",
    "ivorycoast": "Ivory Coast", "côted'ivoire": "Ivory Coast", "cotedivoire": "Ivory Coast",
    "ecuador": "Ecuador", "netherlands": "Netherlands", "japan": "Japan",
    "sweden": "Sweden", "tunisia": "Tunisia", "belgium": "Belgium", "egypt": "Egypt",
    "iran": "Iran", "newzealand": "New Zealand", "spain": "Spain", "capeverde": "Cape Verde",
    "caboverde": "Cape Verde", "saudiarabia": "Saudi Arabia", "uruguay": "Uruguay",
    "france": "France", "senegal": "Senegal", "norway": "Norway", "iraq": "Iraq",
    "argentina": "Argentina", "algeria": "Algeria", "austria": "Austria",
    "jordan": "Jordan", "portugal": "Portugal", "uzbekistan": "Uzbekistan",
    "colombia": "Colombia", "drcongo": "DR Congo", "congodr": "DR Congo",
    "england": "England", "croatia": "Croatia", "ghana": "Ghana", "panama": "Panama"
}

def standardize_string(val):
    if val is None: return ""
    cleaned = re.sub(r'[\s\xa0\u200b\u200c\u200d]+', '', str(val))
    return cleaned.lower().replace("-", "").replace("_", "").replace(".", "")

def connect_to_sheet(tab_name="sheet1"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("World_Cup_Pool_Data")
    return spreadsheet.worksheet(tab_name) if tab_name != "sheet1" else spreadsheet.sheet1

if "automated_live_cache" not in st.session_state:
    st.session_state["automated_live_cache"] = INITIAL_SEED_STANDINGS
if "cache_status_msg" not in st.session_state:
    st.session_state["cache_status_msg"] = "🔄 Initializing data pipeline..."

@st.cache_data(ttl=600)
def fetch_and_merge_api_data():
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{BASE_URL}?season=2026", headers=headers, timeout=12)
        data = response.json()
        if 'standings' in data and len(data['standings']) > 0:
            updated_map = {}
            for block in data['standings']:
                raw_group_name = block.get('group', '')
                clean_group_key = raw_group_name.replace('_', ' ').title()
                if clean_group_key in INITIAL_SEED_STANDINGS:
                    ordered_teams = []
                    for row in block.get('table', []):
                        team_node = row.get('team', {})
                        raw_name = team_node.get('shortName') or team_node.get('name')
                        if raw_name:
                            lookup = standardize_string(raw_name)
                            clean_name = CLEAN_TEAM_MAP.get(lookup, str(raw_name).strip())
                            ordered_teams.append(clean_name)
                    for team in INITIAL_SEED_STANDINGS[clean_group_key]:
                        if team not in ordered_teams: ordered_teams.append(team)
                    if len(ordered_teams) >= 4: updated_map[clean_group_key] = ordered_teams[:4]
            if len(updated_map) > 0:
                current_memory = dict(st.session_state["automated_live_cache"])
                current_memory.update(updated_map)
                st.session_state["automated_live_cache"] = current_memory
                st.session_state["cache_status_msg"] = f"✅ Sync accurate as of {datetime.now().strftime('%H:%M')}"
                return current_memory, False
        st.session_state["cache_status_msg"] = "📡 API connection delayed. Utilizing last known saved live standings."
        return st.session_state["automated_live_cache"], True
    except Exception:
        st.session_state["cache_status_msg"] = "📡 API connection delayed. Utilizing last known saved live standings."
        return st.session_state["automated_live_cache"], True

# --- APP UI ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation", ["Leaderboard", "Make Predictions", "Rules & Chat Forum"])

with st.sidebar:
    st.header("Player Info")
    user_name = st.text_input("Full Name:")
    st.divider()

if page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    live_standings_map, is_using_memory_fallback = fetch_and_merge_api_data()
    try:
        df = pd.DataFrame(connect_to_sheet().get_all_records())
        rename_dict = {df.columns[0]: 'Timestamp', df.columns[1]: 'Name'}
        for col in df.columns:
            clean_col = re.sub(r'\s+', '', str(col)).upper()
            match = re.match(r'^([A-L][1-4])$', clean_col)
            if match: rename_dict[col] = match.group(1)
            elif clean_col == 'STATUS': rename_dict[col] = 'Status'
        df = df.rename(columns=rename_dict)
        if 'Status' not in df.columns: df['Status'] = 'Pending'
        total_pot = df['Status'].astype(str).str.strip().str.lower().eq('paid').sum() * 10
        
        col1, col2 = st.columns([3, 1])
        with col1: st.info(st.session_state["cache_status_msg"])
        with col2: st.metric(label="💰 Total Pool Pot", value=f"${total_pot} USD")
        
        def calculate_live_user_score(row):
            total_points = 0
            for letter in 'ABCDEFGHIJKL':
                live_order = live_standings_map.get(f"Group {letter}", [])
                if len(live_order) < 4: continue
                for i in range(1, 5):
                    user_pick = CLEAN_TEAM_MAP.get(standardize_string(row.get(f"{letter}{i}", "")), "")
                    if user_pick == live_order[i-1]: total_points += 1
            return total_points

        df['Points'] = df.apply(calculate_live_user_score, axis=1)
        leaderboard_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
        
        st.subheader("Current Standings")
        header_cols = st.columns([2, 1, 1, 2])
        header_cols[0].markdown("**Name**"); header_cols[1].markdown("**Points**"); header_cols[2].markdown("**Status**"); header_cols[3].markdown("**Download**")
        st.divider()
        for _, row in leaderboard_df.iterrows():
            cols = st.columns([2, 1, 1, 2])
            cols[0].write(row['Name']); cols[1].write(row['Points']); cols[2].write(row['Status'])
            csv = df[df['Name'] == row['Name']].to_csv(index=False).encode('utf-8')
            cols[3].download_button("📥 CSV", csv, f"{row['Name']}_picks.csv", key=f"dl_{row['Name']}")
    except Exception as e: st.error(f"Error: {e}")

elif page == "Make Predictions":
    st.title("🏆 2026 World Cup Predictions")
    all_picks, summary_data = [], []
    cols = st.columns(4)
    for i, (g_name, teams) in enumerate(groups.items()):
        with cols[i % 4]:
            st.markdown(f"### {g_name}")
            r1 = st.selectbox("1st", ["--"] + teams, key=f"{g_name}_1")
            r2 = st.selectbox("2nd", ["--"] + [t for t in teams if t != r1], key=f"{g_name}_2")
            r3 = st.selectbox("3rd", ["--"] + [t for t in teams if t != r1 and t != r2], key=f"{g_name}_3")
            r4 = st.selectbox("4th", ["--"] + [t for t in teams if t not in [r1, r2, r3]], key=f"{g_name}_4")
            all_picks.extend([r1, r2, r3, r4])
            summary_data.append({"Group": g_name, "1st": r1, "2nd": r2, "3rd": r3, "4th": r4})

    if st.button("Submit Rankings"):
        if not user_name or "--" in all_picks: st.error("Complete all fields and enter name.")
        else:
            connect_to_sheet().append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_name] + all_picks + ["Pending"])
            st.success("Saved!"); st.balloons()

elif page == "Rules & Chat Forum":
    st.title("📜 Rules & Chat Forum")
    try:
        messages = connect_to_sheet("Chat_Data").get_all_records()
        for msg in reversed(messages[-15:]):
            st.markdown(f"**{msg['User']}** ({msg['Timestamp']})"); st.write(msg['Message']); st.divider()
    except: st.warning("Chat unavailable.")
