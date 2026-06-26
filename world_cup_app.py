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
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e

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
        except gspread.exceptions.APIError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                st.error("⚠️ Could not load player list from Google Sheets.")
                return []
        except Exception as e:
            st.error(f"⚠️ Unexpected error loading players: {e}")
            return []

def save_pick_with_retry(ko_sheet, row_i, new_row, retries=3):
    for attempt in range(retries):
        try:
            if row_i != -1:
                ko_sheet.update(range_name=f"A{row_i}:G{row_i}", values=[new_row])
            else:
                ko_sheet.append_row(new_row)
            return True
        except gspread.exceptions.APIError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return False

@st.cache_data(ttl=10800)
def fetch_and_merge_api_data():
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(f"{BASE_URL}?season=2026", headers=headers, timeout=12)
    if response.status_code != 200: raise Exception(f"HTTP Error {response.status_code}")
    data = response.json()
    updated_map = {}
    for block in data.get('standings', []):
        clean_group_key = None
        raw_group_name = block.get('group')
        if raw_group_name:
            group_str = str(raw_group_name).upper()
            match = re.search(r'\b([A-L])\b|GROUP[\s_-]*([A-L])', group_str)
            if match: clean_group_key = f"Group {match.group(1) or match.group(2)}"
        if clean_group_key in INITIAL_SEED_STANDINGS:
            ordered_teams = []
            for row in block.get('table', []):
                team_node = row.get('team', {})
                raw_name = team_node.get('shortName') or team_node.get('name')
                if raw_name: ordered_teams.append(CLEAN_TEAM_MAP.get(standardize_string(raw_name), raw_name))
            for team in INITIAL_SEED_STANDINGS[clean_group_key]:
                if team not in ordered_teams: ordered_teams.append(team)
            if len(ordered_teams) >= 4: updated_map[clean_group_key] = ordered_teams[:4]
    return updated_map

@st.cache_data(ttl=1800)
def fetch_live_matches_api():
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{MATCHES_URL}?season=2026", headers=headers, timeout=12)
        if response.status_code == 200: return response.json().get('matches', [])
    except Exception as e:
        st.warning(f"⚠️ Could not fetch live match data: {e}")
    return []

st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation Menu", ["Knockout Predictions", "Leaderboard", "Group Predictions (Closed)", "Rules & Chat Forum"])
registered_players = get_registered_players()

with st.sidebar:
    st.header("Player Login")
    if registered_players:
        selected_dropdown_name = st.selectbox("Identify Profile Name:", ["-- Select Profile --"] + registered_players)
        user_name = selected_dropdown_name if selected_dropdown_name != "-- Select Profile --" else ""
    else:
        st.warning("⚠️ Could not load player list.")
        user_name = ""
    st.divider()
    if st.button("🔄 Clear System Cache / Sync Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if "ko_winners" not in st.session_state: st.session_state.ko_winners = {}

if page == "Knockout Predictions":
    st.title("🏆 Interactive Knockout Bracket Engine")
    if not user_name:
        st.info("👈 Authenticate to open your bracket.")
    else:
        st.success(f"Log-In User: **{user_name}**")
        try:
            ko_sheet = connect_to_sheet("Knockout_Picks")
        except Exception as e:
            st.error(f"❌ Could not connect to picks sheet: {e}")
            st.stop()

        user_ko_df = pd.DataFrame(ko_sheet.get_all_records())
        if not user_ko_df.empty:
            user_ko_df = user_ko_df[user_ko_df['Name'].astype(str).str.lower() == user_name.strip().lower()]

        raw_matches = fetch_live_matches_api()

        def draw_match_ui(tag, home, away, is_locked, match_no, date, stage):
            exist_row = user_ko_df[user_ko_df['Match_ID'].astype(str) == tag] if not user_ko_df.empty else pd.DataFrame()
            default_h = int(exist_row['Home_Score'].values[0]) if not exist_row.empty else 0
            default_a = int(exist_row['Away_Score'].values[0]) if not exist_row.empty else 0
            default_w = str(exist_row['Winner'].values[0]) if not exist_row.empty else home
            
            # Logic: Green border if both teams known and not TBD
            is_ready = "TBD" not in [home, away]
            border_style = "2px solid #2ecc71" if is_ready else "1px solid #ccc"

            with st.container(border=True):
                # CSS for border
                st.markdown(f"""<style>[data-testid="stVerticalBlock"]:has(> div > p > b:contains("{home}")) {{ border: {border_style} !important; border-radius: 5px; }}</style>""", unsafe_allow_html=True)
                
                if date: st.caption(f"📅 Match {match_no} • {date}")
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
                
                # Lock/Update Button + Status Indicator
                sub_c1, sub_c2 = st.columns([2, 2])
                with sub_c1:
                    if st.button("Lock Score", key=f"btn_s_{tag}", disabled=is_locked):
                        row_i = next((i + 2 for i, r in enumerate(ko_sheet.get_all_records()) if str(r.get('Name')).lower() == user_name.lower() and str(r.get('Match_ID')) == tag), -1)
                        new_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_name.strip(), tag, int(h_score), int(a_score), chosen_winner, stage]
                        success = save_pick_with_retry(ko_sheet, row_i, new_row)
                        if success:
                            st.toast("✅ Saved!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save.")
                
                with sub_c2:
                    if not exist_row.empty:
                        st.markdown("🟢 **Submitted**")

        st.subheader("1️⃣ Round of 32")
        api_r32 = sorted([m for m in raw_matches if m.get('stage') == "ROUND_OF_32"], key=lambda x: x.get('utcDate', ''))
        for idx, f in enumerate(FIXED_R32_MATCHES):
            tag = str(api_r32[idx].get('id')) if idx < len(api_r32) else f['id_tag']
            h = CLEAN_TEAM_MAP.get(standardize_string(api_r32[idx].get('homeTeam', {}).get('name')), f['home']) if idx < len(api_r32) else f['home']
            a = CLEAN_TEAM_MAP.get(standardize_string(api_r32[idx].get('awayTeam', {}).get('name')), f['away']) if idx < len(api_r32) else f['away']
            draw_match_ui(tag, h, a, (idx < len(api_r32) and api_r32[idx].get('status') not in ["TIMED", "SCHEDULED"]), f['match_no'], f['date'], "ROUND_OF_32")

        for stage, label in [("ROUND_OF_16", "2️⃣ R16"), ("QUARTER_FINALS", "3️⃣ QF"), ("SEMI_FINALS", "4️⃣ SF"), ("FINAL", "5️⃣ Final")]:
            st.subheader(label)
            for m_id, src in BRACKET_MAPPING.get(stage, {}).items():
                draw_match_ui(m_id, st.session_state.ko_winners.get(src[0], f"Winner {src[0]}"), st.session_state.ko_winners.get(src[1], f"Winner {src[1]}"), False, 0, None, stage)

        st.write("---")
        st.subheader("🏁 Tie-Breaker")
        tb_val = st.number_input("Total goals in knockout stage:", min_value=0, value=int(user_ko_df[user_ko_df['Match_ID'] == 'TIE_BREAKER']['Home_Score'].iloc[0] if 'TIE_BREAKER' in user_ko_df['Match_ID'].values else 0))
        if st.button("Submit Tie-Breaker"):
            success = save_pick_with_retry(ko_sheet, -1, [datetime.now().strftime("%Y-%m-%d"), user_name, "TIE_BREAKER", tb_val, 0, "N/A", "TIE"])
            if success:
                st.success("Tie-breaker submitted!")
                st.rerun()
            else:
                st.error("❌ Failed to save.")

elif page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    live_matches = fetch_live_matches_api()
    try:
        all_picks = pd.DataFrame(connect_to_sheet("Knockout_Picks").get_all_records())
    except Exception as e:
        st.error(f"❌ Could not load picks: {e}")
        st.stop()

    def calc_score(row):
        score = 0
        u_picks = all_picks[all_picks['Name'].str.lower() == str(row['Name']).lower()]
        for _, p in u_picks.iterrows():
            m = next((m for m in live_matches if str(m.get('id')) == str(p['Match_ID'])), None)
            if m and m.get('status') == 'FINISHED':
                ft = m.get('score', {}).get('fullTime', {})
                if str(p['Home_Score']) == str(ft.get('home')): score += 1
                if str(p['Away_Score']) == str(ft.get('away')): score += 1
                actual_winner = "HOME" if ft.get('home') > ft.get('away') else "AWAY"
                pick_winner = "HOME" if p['Home_Score'] > p['Away_Score'] else "AWAY"
                if actual_winner == pick_winner: score += 1
        return score

    try:
        df = pd.DataFrame(connect_to_sheet("sheet1").get_all_records())
        df['Points'] = df.apply(calc_score, axis=1)
        st.table(df[['Name', 'Points']].sort_values(by='Points', ascending=False))
    except Exception as e:
        st.error(f"❌ Could not load leaderboard: {e}")

elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules")
    st.write("**Formula:** 1 pt/correct winner, 1 pt/exact home score, 1 pt/exact away score.")
