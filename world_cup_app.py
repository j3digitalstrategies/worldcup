import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

# --- GLOBAL POOL CONFIGURATION ---
API_KEY = '63ba1313af494222bddfb7f14879b920' 
BASE_URL = "https://api.football-data.org/v4/competitions/WC/standings"
MATCHES_URL = "https://api.football-data.org/v4/competitions/WC/matches"

# --- OFFICIAL 2026 GROUP TEAM CONFIGURATIONS ---
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

FIXED_R32_MATCHES = [
    {"match_no": 1, "date": "Sun, 28 Jun, 21:00", "home": "South Africa", "away": "Canada", "id_tag": "M73"},
    {"match_no": 2, "date": "Mon, 29 Jun, 19:00", "home": "Brazil", "away": "Japan", "id_tag": "M74"},
    {"match_no": 3, "date": "Mon, 29 Jun, 22:30", "home": "Germany", "away": "TBD", "id_tag": "M75"},
    {"match_no": 4, "date": "Tue, 30 Jun, 03:00", "home": "Netherlands", "away": "Morocco", "id_tag": "M76"},
    {"match_no": 5, "date": "Tue, 30 Jun, 19:00", "home": "Côte d'Ivoire", "away": "TBD", "id_tag": "M77"},
    {"match_no": 6, "date": "Tue, 30 Jun, 23:00", "home": "TBD", "away": "TBD", "id_tag": "M78"},
    {"match_no": 7, "date": "Wed, 1 Jul, 03:00", "home": "Mexico", "away": "TBD", "id_tag": "M79"},
    {"match_no": 8, "date": "Wed, 1 Jul, 18:00", "home": "TBD", "away": "TBD", "id_tag": "M80"},
    {"match_no": 9, "date": "Wed, 1 Jul, 22:00", "home": "TBD", "away": "TBD", "id_tag": "M81"},
    {"match_no": 10, "date": "Thu, 2 Jul, 02:00", "home": "USA", "away": "Bosnia and Herzegovina", "id_tag": "M82"},
    {"match_no": 11, "date": "Thu, 2 Jul, 21:00", "home": "TBD", "away": "TBD", "id_tag": "M83"},
    {"match_no": 12, "date": "Fri, 3 Jul, 01:00", "home": "TBD", "away": "TBD", "id_tag": "M84"},
    {"match_no": 13, "date": "Fri, 3 Jul, 05:00", "home": "Switzerland", "away": "TBD", "id_tag": "M85"},
    {"match_no": 14, "date": "Fri, 3 Jul, 20:00", "home": "Australia", "away": "TBD", "id_tag": "M86"},
    {"match_no": 15, "date": "Sat, 4 Jul, 00:00", "home": "Argentina", "away": "TBD", "id_tag": "M87"},
    {"match_no": 16, "date": "Sat, 4 Jul, 03:30", "home": "TBD", "away": "TBD", "id_tag": "M88"}
]

BRACKET_MAPPING = {
    "ROUND_OF_16": {"M89": ("M73", "M76"), "M90": ("M74", "M77"), "M91": ("M75", "M82"), "M92": ("M78", "M79"), "M93": ("M80", "M81"), "M94": ("M83", "M84"), "M95": ("M85", "M86"), "M96": ("M87", "M88")},
    "QUARTER_FINALS": {"M97": ("M89", "M90"), "M98": ("M91", "M92"), "M99": ("M93", "M94"), "M100": ("M95", "M96")},
    "SEMI_FINALS": {"M101": ("M97", "M98"), "M102": ("M99", "M100")},
    "FINAL": {"M104": ("M101", "M102")}
}

# --- UTILITIES ---
def standardize_string(val):
    if val is None: return ""
    return re.sub(r'[\s\xa0\u200b\u200c\u200d]+', '', str(val)).lower().replace("-", "").replace("_", "").replace(".", "")

@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    return gspread.authorize(creds)

@st.cache_resource
def get_spreadsheet():
    # REPLACE THIS WITH YOUR ACTUAL SHEET ID FROM THE URL
    return get_gspread_client().open_by_key("YOUR_ACTUAL_SPREADSHEET_KEY_HERE")

def connect_to_sheet(tab_name="sheet1"):
    spreadsheet = get_spreadsheet()
    try: return spreadsheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        if tab_name == "Knockout_Picks":
            ws = spreadsheet.add_worksheet(title="Knockout_Picks", rows="1000", cols="7")
            ws.append_row(["Timestamp", "Name", "Match_ID", "Home_Score", "Away_Score", "Winner", "Stage"])
            return ws
        return spreadsheet.sheet1

@st.cache_data(ttl=10800)
def fetch_and_merge_api_data():
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{BASE_URL}?season=2026", headers=headers, timeout=12)
        if response.status_code != 200: return {}
        data = response.json()
        updated_map = {}
        for block in data.get('standings', []):
            raw_group_name = block.get('group') or ""
            match = re.search(r'\b([A-L])\b', str(raw_group_name).upper())
            if match:
                key = f"Group {match.group(1)}"
                ordered = [CLEAN_TEAM_MAP.get(standardize_string(row.get('team', {}).get('name')), row.get('team', {}).get('name')) for row in block.get('table', [])]
                updated_map[key] = ordered
        return updated_map
    except: return {}

@st.cache_data(ttl=1800)
def fetch_live_matches_api():
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{MATCHES_URL}?season=2026", headers=headers, timeout=12)
        if response.status_code == 200: return response.json().get('matches', [])
    except: pass
    return []

# --- MAIN APP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation Menu", ["Knockout Predictions", "Leaderboard", "Group Predictions (Closed)", "Rules & Chat Forum"])
registered_players = sorted([str(r.get(list(r.keys())[1])) for r in connect_to_sheet("sheet1").get_all_records() if len(r.keys()) > 1])
user_name = st.sidebar.selectbox("Identify Profile Name:", ["-- Select Profile --"] + registered_players)

if "ko_winners" not in st.session_state: st.session_state.ko_winners = {}

if page == "Knockout Predictions" and user_name != "-- Select Profile --":
    st.title("🏆 Interactive Knockout Bracket Engine")
    ko_sheet = connect_to_sheet("Knockout_Picks")
    user_ko_df = pd.DataFrame(ko_sheet.get_all_records())
    user_ko_df = user_ko_df[user_ko_df['Name'].astype(str).str.lower() == user_name.strip().lower()] if not user_ko_df.empty else pd.DataFrame()
    raw_matches = fetch_live_matches_api()

    def draw_match_ui(tag, home, away, is_locked, match_no, date, stage):
        exist = user_ko_df[user_ko_df['Match_ID'].astype(str) == tag]
        dh, da = (int(exist['Home_Score'].iloc[0]), int(exist['Away_Score'].iloc[0])) if not exist.empty else (0, 0)
        dw = str(exist['Winner'].iloc[0]) if not exist.empty else home
        with st.container(border=True):
            if date: st.caption(f"📅 Match {match_no} • {date}")
            c1, c2, c3, c4 = st.columns([3, 1, 3, 3])
            with c1:
                st.markdown(f"**{home}**")
                hs = st.number_input("Goals", min_value=0, value=dh, key=f"h_{tag}", disabled=is_locked)
            with c2: st.markdown("<br><p style='text-align:center;'>VS</p>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"**{away}**")
                as_ = st.number_input("Goals", min_value=0, value=da, key=f"a_{tag}", disabled=is_locked)
            with c4:
                cw = st.selectbox("Advances:", [home, away], index=[home, away].index(dw) if dw in [home, away] else 0, key=f"pk_{tag}", disabled=is_locked) if hs == as_ else (home if hs > as_ else away)
                if hs != as_: st.markdown(f"<br><p><b>Advances:</b> {cw}</p>", unsafe_allow_html=True)
            st.session_state.ko_winners[tag] = cw
            if not is_locked and st.button("Lock Score", key=f"btn_{tag}"):
                ko_sheet.append_row([datetime.now().strftime("%Y-%m-%d"), user_name, tag, hs, as_, cw, stage])
                st.toast("Saved!")

    st.subheader("1️⃣ Round of 32")
    api_r32 = sorted([m for m in raw_matches if m.get('stage') == "ROUND_OF_32"], key=lambda x: x.get('utcDate', ''))
    for idx, f in enumerate(FIXED_R32_MATCHES):
        draw_match_ui(str(api_r32[idx]['id']) if idx < len(api_r32) else f['id_tag'], f['home'], f['away'], False, f['match_no'], f['date'], "ROUND_OF_32")

    for stage, label in [("ROUND_OF_16", "2️⃣ R16"), ("QUARTER_FINALS", "3️⃣ QF"), ("SEMI_FINALS", "4️⃣ SF"), ("FINAL", "5️⃣ Final")]:
        st.subheader(label)
        for m_id, src in BRACKET_MAPPING.get(stage, {}).items():
            draw_match_ui(m_id, st.session_state.ko_winners.get(src[0], "TBD"), st.session_state.ko_winners.get(src[1], "TBD"), False, 0, None, stage)

elif page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    live_matches = fetch_live_matches_api()
    all_picks = pd.DataFrame(connect_to_sheet("Knockout_Picks").get_all_records())
    df = pd.DataFrame(connect_to_sheet("sheet1").get_all_records())
    
    def calc_score(row):
        score = 0
        u_picks = all_picks[all_picks['Name'].str.lower() == str(row.iloc[1]).lower()]
        for _, p in u_picks.iterrows():
            m = next((m for m in live_matches if str(m.get('id')) == str(p['Match_ID'])), None)
            if m and m.get('status') == 'FINISHED':
                ft = m.get('score', {}).get('fullTime', {})
                if str(p['Home_Score']) == str(ft.get('home')): score += 1
                if str(p['Away_Score']) == str(ft.get('away')): score += 1
                if ("HOME" if ft.get('home') > ft.get('away') else "AWAY") == ("HOME" if p['Home_Score'] > p['Away_Score'] else "AWAY"): score += 1
        return score
    
    df['Points'] = df.apply(calc_score, axis=1)
    st.table(df.sort_values(by='Points', ascending=False))

elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules")
    st.write("Scoring: 1 pt/winner, 1 pt/home goal, 1 pt/away goal.")
