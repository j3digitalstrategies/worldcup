import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import time

# --- GLOBAL POOL CONFIGURATION ---
API_KEY = '63ba1313af494222bddfb7f14879b920'
BASE_URL = "https://api.football-data.org/v4/competitions/WC/standings"
MATCHES_URL = "https://api.football-data.org/v4/competitions/WC/matches"
SHEET_KEY = "1n8UR-kAVKeIuTTfl6AQPYeLlOy_iEruvdRSfYykIO8E"

# Helper for Team Normalization
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

BRACKET_MAPPING = {
    "ROUND_OF_16": {"M89": ("M73", "M76"), "M90": ("M74", "M77"), "M91": ("M75", "M82"), "M92": ("M78", "M79"), "M93": ("M80", "M81"), "M94": ("M83", "M84"), "M95": ("M85", "M86"), "M96": ("M87", "M88")},
    "QUARTER_FINALS": {"M97": ("M89", "M90"), "M98": ("M91", "M92"), "M99": ("M93", "M94"), "M100": ("M95", "M96")},
    "SEMI_FINALS": {"M101": ("M97", "M98"), "M102": ("M99", "M100")},
    "FINAL": {"M104": ("M101", "M102")}
}

def standardize_string(val):
    if val is None: return ""
    cleaned = re.sub(r'[\s\xa0\u200b\u200c\u200d]+', '', str(val))
    return cleaned.lower().replace("-", "").replace("_", "").replace(".", "")

def connect_to_sheet(tab_name="sheet1", retries=3):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    for attempt in range(retries):
        try:
            creds_dict = st.secrets["gcp_service_account"]
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(SHEET_KEY)
            if tab_name == "Knockout_Picks":
                try:
                    return spreadsheet.worksheet("Knockout_Picks")
                except gspread.exceptions.WorksheetNotFound:
                    new_tab = spreadsheet.add_worksheet(title="Knockout_Picks", rows="1000", cols="7")
                    new_tab.append_row(["Timestamp", "Name", "Match_ID", "Home_Score", "Away_Score", "Winner", "Stage"])
                    return new_tab
            return spreadsheet.sheet1 if tab_name == "sheet1" else spreadsheet.worksheet(tab_name)
        except gspread.exceptions.APIError as e:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            else: raise e

def get_registered_players(retries=3):
    for attempt in range(retries):
        try:
            sheet = connect_to_sheet("sheet1")
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                if len(df.columns) >= 2:
                    return sorted(list(df['Name'].astype(str).str.strip().unique()))
            return []
        except:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            return []

def save_pick_with_retry(ko_sheet, row_i, new_row, retries=3):
    for attempt in range(retries):
        try:
            if row_i != -1: ko_sheet.update(range_name=f"A{row_i}:G{row_i}", values=[new_row])
            else: ko_sheet.append_row(new_row)
            return True
        except:
            if attempt < retries - 1: time.sleep(2 ** attempt)
            return False

@st.cache_data(ttl=1800)
def fetch_live_matches_api():
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{MATCHES_URL}?season=2026", headers=headers, timeout=12)
        if response.status_code == 200: return response.json().get('matches', [])
    except:
        return []

st.set_page_config(page_title="2026 WC Portal", layout="wide")

# Sidebar and User Selection
with st.sidebar:
    st.header("Player Login")
    registered_players = get_registered_players()
    
    if registered_players:
        selected_dropdown_name = st.selectbox("Identify Profile Name:", ["-- Select Profile --"] + registered_players)
        user_name = selected_dropdown_name if selected_dropdown_name != "-- Select Profile --" else ""
    else:
        user_name = ""
    
    st.divider()
    if st.button("🔄 Clear Cache / Refresh Data"):
        st.cache_data.clear()
        st.rerun()

page = st.sidebar.radio("Navigation Menu", ["Knockout Predictions", "Leaderboard", "Group Predictions (Closed)", "Rules & Chat Forum"])

if "ko_winners" not in st.session_state: st.session_state.ko_winners = {}

# --- Dynamic Match Parsing Helper ---
def get_dynamic_r32_matches(all_matches):
    """Filters API matches for R32/Last 16 and maps them to M73-M88 IDs."""
    ko_list = [m for m in all_matches if str(m.get('stage', '')).upper() in ['ROUND_OF_32', 'LAST_16', 'KNOCKOUT']]
    ko_list.sort(key=lambda x: x.get('utcDate', '9999-12-31'))
    
    mapped = {}
    for i in range(16):
        match_id = f"M{73 + i}"
        if i < len(ko_list):
            m = ko_list[i]
            mapped[match_id] = {
                "api_match": m,
                "home": CLEAN_TEAM_MAP.get(standardize_string(m.get('homeTeam', {}).get('name')), m.get('homeTeam', {}).get('name', 'TBD')),
                "away": CLEAN_TEAM_MAP.get(standardize_string(m.get('awayTeam', {}).get('name')), m.get('awayTeam', {}).get('name', 'TBD')),
                "date": m.get('utcDate', '')
            }
        else:
            mapped[match_id] = {"api_match": None, "home": "TBD", "away": "TBD", "date": None}
    return mapped

if page == "Knockout Predictions":
    st.title("🏆 Interactive Knockout Bracket Engine")
    if not user_name:
        st.info("👈 Authenticate to open your bracket.")
    else:
        st.success(f"Log-In User: **{user_name}**")
        ko_sheet = connect_to_sheet("Knockout_Picks")
        user_ko_df = pd.DataFrame(ko_sheet.get_all_records())
        if not user_ko_df.empty:
            user_ko_df = user_ko_df[user_ko_df['Name'].astype(str).str.lower() == user_name.strip().lower()]
            for _, row in user_ko_df.iterrows():
                st.session_state.ko_winners[str(row['Match_ID'])] = str(row['Winner'])

        raw_matches = fetch_live_matches_api()
        dynamic_matches = get_dynamic_r32_matches(raw_matches)

        def draw_match_ui(tag, home, away, is_locked, stage):
            exist_row = user_ko_df[user_ko_df['Match_ID'].astype(str) == tag] if not user_ko_df.empty else pd.DataFrame()
            default_h = int(exist_row['Home_Score'].values[0]) if not exist_row.empty else 0
            default_a = int(exist_row['Away_Score'].values[0]) if not exist_row.empty else 0
            default_w = str(exist_row['Winner'].values[0]) if not exist_row.empty else home
            
            with st.container():
                st.write("---")
                c1, c2, c3, c4 = st.columns([3, 1, 3, 3])
                with c1:
                    st.markdown(f"**{home}**")
                    h_score = st.number_input("Goals", min_value=0, value=default_h, key=f"h_s_{tag}", disabled=is_locked)
                with c2: st.markdown("<br><p style='text-align:center;'>VS</p>", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"**{away}**")
                    a_score = st.number_input("Goals", min_value=0, value=default_a, key=f"a_s_{tag}", disabled=is_locked)
                with c4:
                    if h_score == a_score:
                        chosen_winner = st.selectbox("Advances via PKs:", [home, away], index=[home, away].index(default_w) if default_w in [home, away] else 0, key=f"pk_w_{tag}", disabled=is_locked)
                    else:
                        chosen_winner = home if h_score > a_score else away
                        st.markdown(f"<br><p><b>Advances:</b> {chosen_winner}</p>", unsafe_allow_html=True)
                st.session_state.ko_winners[tag] = chosen_winner
                
                if st.button("Lock Score", key=f"btn_s_{tag}", disabled=is_locked):
                    row_i = next((i + 2 for i, r in enumerate(ko_sheet.get_all_records()) if str(r.get('Name')).lower() == user_name.lower() and str(r.get('Match_ID')) == tag), -1)
                    new_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_name.strip(), tag, int(h_score), int(a_score), chosen_winner, stage]
                    if save_pick_with_retry(ko_sheet, row_i, new_row): st.rerun()

        st.subheader("1️⃣ Round of 32")
        for tag, info in dynamic_matches.items():
            is_locked = (info['api_match'] and info['api_match'].get('status') not in ["TIMED", "SCHEDULED"])
            draw_match_ui(tag, info['home'], info['away'], is_locked, "ROUND_OF_32")

        for stage, label in [("ROUND_OF_16", "2️⃣ R16"), ("QUARTER_FINALS", "3️⃣ QF"), ("SEMI_FINALS", "4️⃣ SF"), ("FINAL", "5️⃣ Final")]:
            st.subheader(label)
            for m_id, src in BRACKET_MAPPING.get(stage, {}).items():
                draw_match_ui(m_id, st.session_state.ko_winners.get(src[0], f"Winner {src[0]}"), st.session_state.ko_winners.get(src[1], f"Winner {src[1]}"), False, stage)

elif page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    all_picks = pd.DataFrame(connect_to_sheet("Knockout_Picks").get_all_records())
    raw_matches = fetch_live_matches_api()
    dynamic_matches = get_dynamic_r32_matches(raw_matches)
    
    # Create lookup for points
    def calc_score(row):
        score = 0
        u_picks = all_picks[all_picks['Name'].astype(str).str.lower() == str(row['Name']).lower()]
        for _, p in u_picks.iterrows():
            m_data = dynamic_matches.get(str(p['Match_ID']))
            if m_data and m_data['api_match'] and m_data['api_match'].get('status') in ['FINISHED', 'AWARDED']:
                ft = m_data['api_match'].get('score', {}).get('fullTime', {})
                if str(p['Home_Score']) == str(ft.get('home')): score += 1
                if str(p['Away_Score']) == str(ft.get('away')): score += 1
                
                api_winner = m_data['api_match'].get('score', {}).get('winner')
                # Simplified winner logic
                if api_winner == 'HOME_TEAM' and standardize_string(str(p['Winner'])) == standardize_string(m_data['home']): score += 1
                elif api_winner == 'AWAY_TEAM' and standardize_string(str(p['Winner'])) == standardize_string(m_data['away']): score += 1
        return score

    df = pd.DataFrame(connect_to_sheet("sheet1").get_all_records())
    if not df.empty:
        df['Points'] = df.apply(calc_score, axis=1)
        st.table(df[['Name', 'Points']].sort_values(by='Points', ascending=False))

elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules")
    st.write("**Formula:** 1 pt/correct winner, 1 pt/exact home score, 1 pt/exact away score. (Max 3 points per match)")
