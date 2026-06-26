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

# --- MASTER CHRONOLOGICAL TEMPLATE (Your Known Matches) ---
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

# --- BRACKET LINKAGE PATHS (How winners cascade forward) ---
BRACKET_MAPPING = {
    "ROUND_OF_16": {
        "M89": ("M73", "M76"),  # Winner Match 1 vs Winner Match 4
        "M90": ("M74", "M77"),  # Winner Match 2 vs Winner Match 5
        "M91": ("M75", "M82"),  # Winner Match 3 vs Winner Match 10
        "M92": ("M78", "M79"),
        "M93": ("M80", "M81"),
        "M94": ("M83", "M84"),
        "M95": ("M85", "M86"),
        "M96": ("M87", "M88"),
    },
    "QUARTER_FINALS": {
        "M97": ("M89", "M90"),
        "M98": ("M91", "M92"),
        "M99": ("M93", "M94"),
        "M100": ("M95", "M96"),
    },
    "SEMI_FINALS": {
        "M101": ("M97", "M98"),
        "M102": ("M99", "M100"),
    },
    "FINAL": {
        "M104": ("M101", "M102")
    }
}

# --- COMPONENT LOGIC & UTILITIES ---
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
    
    if tab_name == "Knockout_Picks":
        try:
            return spreadsheet.worksheet("Knockout_Picks")
        except gspread.exceptions.WorksheetNotFound:
            new_tab = spreadsheet.add_worksheet(title="Knockout_Picks", rows="1000", cols="7")
            new_tab.append_row(["Timestamp", "Name", "Match_ID", "Home_Score", "Away_Score", "Winner", "Stage"])
            return new_tab
    return spreadsheet.sheet1 if tab_name == "sheet1" else spreadsheet.worksheet(tab_name)

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
    except: pass
    return []

def get_registered_players():
    try:
        sheet = connect_to_sheet("sheet1")
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            if len(df.columns) >= 2: return sorted(list(df[df.columns[1]].astype(str).str.strip().unique()))
    except: pass
    return []

# --- MAIN APP LAYOUT SETUP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation Menu", ["Knockout Predictions", "Leaderboard", "Group Predictions (Closed)", "Rules & Chat Forum"])
registered_players = get_registered_players()

with st.sidebar:
    st.header("Player Login")
    if registered_players:
        selected_dropdown_name = st.selectbox("Identify Profile Name:", ["-- Select Profile --"] + registered_players)
        user_name = selected_dropdown_name if selected_dropdown_name != "-- Select Profile --" else ""
    else:
        st.warning("⚠️ No names detected on registration sheet.")
        user_name = ""
    st.divider()
    if st.button("🔄 Clear System Cache / Sync Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- INITIALIZE RUNTIME BRACKET WINNERS DICTIONARY ---
if "ko_winners" not in st.session_state:
    st.session_state.ko_winners = {}

# --- PAGE 1: KNOCKOUT PREDICTIONS (DYNAMIC MATRIX CASCADING WHEEL) ---
if page == "Knockout Predictions":
    st.title("🏆 Interactive Knockout Bracket Engine")
    st.markdown("Your picks are checked and processed down the stream. Selecting a winner auto-allocates the upcoming opponent choices in real time.")
    
    if not user_name:
        st.info("👈 Please authenticate your name from the dropdown choice in the sidebar to open your bracket.")
    else:
        st.success(f"Log-In User: **{user_name}**")
        
        ko_records = []
        try:
            ko_sheet = connect_to_sheet("Knockout_Picks")
            ko_records = ko_sheet.get_all_records()
        except: pass
        user_ko_df = pd.DataFrame(ko_records)
        if not user_ko_df.empty:
            user_ko_df = user_ko_df[user_ko_df['Name'].astype(str).str.lower() == user_name.strip().lower()]

        raw_matches = fetch_live_matches_api()
        api_r32 = sorted([m for m in raw_matches if m.get('stage') == "ROUND_OF_32"], key=lambda x: x.get('utcDate', ''))

        # --- TIER 1: ROUND OF 32 ---
        st.subheader("1️⃣ Round of 32")
        for idx, fallback in enumerate(FIXED_R32_MATCHES):
            tag = fallback['id_tag']
            is_locked = False
            home_team = fallback['home']
            away_team = fallback['away']
            
            # Match directly with chronological index array fields inside the raw API structure
            if idx < len(api_r32):
                api_m = api_r32[idx]
                tag = str(api_m.get('id'))
                is_locked = api_m.get('status') not in ["TIMED", "SCHEDULED"]
                api_h = api_m.get('homeTeam', {}).get('name') or ""
                api_a = api_m.get('awayTeam', {}).get('name') or ""
                if api_h and not any(x in api_h.lower() for x in ["winner", "runner-up", "tbd", "placeholder"]):
                    home_team = CLEAN_TEAM_MAP.get(standardize_string(api_h), api_h)
                if api_a and not any(x in api_a.lower() for x in ["winner", "runner-up", "tbd", "placeholder"]):
                    away_team = CLEAN_TEAM_MAP.get(standardize_string(api_a), api_a)

            exist_row = user_ko_df[user_ko_df['Match_ID'].astype(str) == tag] if not user_ko_df.empty else pd.DataFrame()
            default_h = int(exist_row['Home_Score'].values[0]) if not exist_row.empty else 0
            default_a = int(exist_row['Away_Score'].values[0]) if not exist_row.empty else 0
            default_w = str(exist_row['Winner'].values[0]) if not exist_row.empty else home_team

            with st.container(border=True):
                st.caption(f"📅 Match {fallback['match_no']} • {fallback['date']}")
                c1, c2, c3, c4 = st.columns([3, 1, 3, 3])
                with c1:
                    h_score = st.number_input("Goals", min_value=0, value=default_h, key=f"h_s_{tag}", disabled=is_locked)
                    st.markdown(f"**{home_team}**")
                with c2: st.markdown("<p style='text-align:center; padding-top:25px;'>VS</p>", unsafe_allow_html=True)
                with c3:
                    a_score = st.number_input("Goals", min_value=0, value=default_a, key=f"a_s_{tag}", disabled=is_locked)
                    st.markdown(f"**{away_team}**")
                with c4:
                    if h_score == a_score:
                        opts = [home_team, away_team]
                        w_idx = opts.index(default_w) if default_w in opts else 0
                        chosen_winner = st.selectbox("Advances via PKs:", opts, index=w_idx, key=f"pk_w_{tag}", disabled=is_locked)
                    else:
                        chosen_winner = home_team if h_score > a_score else away_team
                        st.markdown(f"<p style='padding-top:30px;'><b>Advances:</b> {chosen_winner}</p>", unsafe_allow_html=True)
                
                st.session_state.ko_winners[tag] = chosen_winner
                
                if not is_locked:
                    if st.button("Lock Score Selection", key=f"btn_s_{tag}"):
                        try:
                            ko_sheet = connect_to_sheet("Knockout_Picks")
                            full_ko = ko_sheet.get_all_records()
                            row_i = -1
                            for idx_r, r in enumerate(full_ko):
                                if str(r.get('Name')).strip().lower() == user_name.strip().lower() and str(r.get('Match_ID')) == tag:
                                    row_i = idx_r + 2
                                    break
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_row = [timestamp, user_name.strip(), tag, int(h_score), int(a_score), chosen_winner, "ROUND_OF_32"]
                            if row_i != -1: ko_sheet.update(range_name=f"A{row_i}:G{row_i}", values=[new_row])
                            else: ko_sheet.append_row(new_row)
                            st.toast("Saved successfully!", icon="✅")
                        except Exception as ex: st.error(f"Save error: {ex}")

        # --- TIERS 2-5: DYNAMIC STRUCTURAL CASCADING GROUPS ---
        stages_list = [("ROUND_OF_16", "2️⃣ Round of 16"), ("QUARTER_FINALS", "3️⃣ Quarterfinals"), ("SEMI_FINALS", "4️⃣ Semifinals"), ("FINAL", "5️⃣ World Cup Final")]
        
        for stage_key, stage_label in stages_list:
            st.write("---")
            st.subheader(stage_label)
            
            api_stage_matches = sorted([m for m in raw_matches if m.get('stage') == stage_key], key=lambda x: x.get('utcDate', ''))
            
            for index, (m_id, sources) in enumerate(BRACKET_MAPPING[stage_key].items()):
                # Dynamic validation: fetch actual selections from predecessors
                t1_fallback = st.session_state.ko_winners.get(sources[0], f"Winner {sources[0]}")
                t2_fallback = st.session_state.ko_winners.get(sources[1], f"Winner {sources[1]}")
                
                is_locked = False
                if index < len(api_stage_matches):
                    api_m = api_stage_matches[index]
                    m_id = str(api_m.get('id'))
                    is_locked = api_m.get('status') not in ["TIMED", "SCHEDULED"]
                    api_h = api_m.get('homeTeam', {}).get('name') or ""
                    api_a = api_m.get('awayTeam', {}).get('name') or ""
                    if api_h and not any(x in api_h.lower() for x in ["winner", "runner-up", "tbd"]): t1_fallback = CLEAN_TEAM_MAP.get(standardize_string(api_h), api_h)
                    if api_a and not any(x in api_a.lower() for x in ["winner", "runner-up", "tbd"]): t2_fallback = CLEAN_TEAM_MAP.get(standardize_string(api_a), api_a)

                exist_row = user_ko_df[user_ko_df['Match_ID'].astype(str) == m_id] if not user_ko_df.empty else pd.DataFrame()
                default_h = int(exist_row['Home_Score'].values[0]) if not exist_row.empty else 0
                default_a = int(exist_row['Away_Score'].values[0]) if not exist_row.empty else 0
                default_w = str(exist_row['Winner'].values[0]) if not exist_row.empty else t1_fallback

                with st.container(border=True):
                    st.caption(f"🏆 Match Code Reference Slot: ID {m_id}")
                    c1, c2, c3, c4 = st.columns([3, 1, 3, 3])
                    with c1:
                        h_score = st.number_input("Goals", min_value=0, value=default_h, key=f"h_s_{m_id}", disabled=is_locked)
                        st.markdown(f"**{t1_fallback}**")
                    with c2: st.markdown("<p style='text-align:center; padding-top:25px;'>VS</p>", unsafe_allow_html=True)
                    with c3:
                        a_score = st.number_input("Goals", min_value=0, value=default_a, key=f"a_s_{m_id}", disabled=is_locked)
                        st.markdown(f"**{t2_fallback}**")
                    with c4:
                        if h_score == a_score:
                            opts = [t1_fallback, t2_fallback]
                            w_idx = opts.index(default_w) if default_w in opts else 0
                            chosen_winner = st.selectbox("Advances via PKs:", opts, index=w_idx, key=f"pk_w_{m_id}", disabled=is_locked)
                        else:
                            chosen_winner = t1_fallback if h_score > a_score else t2_fallback
                            st.markdown(f"<p style='padding-top:30px;'><b>Advances:</b> {chosen_winner}</p>", unsafe_allow_html=True)
                    
                    st.session_state.ko_winners[m_id] = chosen_winner
                    
                    if stage_key == "FINAL" and chosen_winner not in ["Winner QF 1", "Winner QF 2", "Winner M101", "Winner M102"]:
                        st.success(f"🏆 **Your Projected World Champion:** {chosen_winner}")
                    
                    if not is_locked:
                        if st.button("Lock Score Selection", key=f"btn_s_{m_id}"):
                            try:
                                ko_sheet = connect_to_sheet("Knockout_Picks")
                                full_ko = ko_sheet.get_all_records()
                                row_i = -1
                                for idx_r, r in enumerate(full_ko):
                                    if str(r.get('Name')).strip().lower() == user_name.strip().lower() and str(r.get('Match_ID')) == m_id:
                                        row_i = idx_r + 2
                                        break
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                new_row = [timestamp, user_name.strip(), m_id, int(h_score), int(a_score), chosen_winner, stage_key]
                                if row_i != -1: ko_sheet.update(range_name=f"A{row_i}:G{row_i}", values=[new_row])
                                else: ko_sheet.append_row(new_row)
                                st.toast("Saved successfully!", icon="✅")
                            except Exception as ex: st.error(f"Save error: {ex}")

# --- PAGE 2: LEADERBOARD ---
elif page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    with st.spinner("Processing point totals..."):
        try:
            live_standings_map = fetch_and_merge_api_data()
            st.success(f"✅ Live Standings Sync Complete")
        except:
            live_standings_map = st.session_state["automated_live_cache"]
            st.info("📡 Running on cache mode.")
            
        live_matches_list = fetch_live_matches_api()
        all_ko_picks = []
        try:
            ko_sheet = connect_to_sheet("Knockout_Picks")
            all_ko_picks = ko_sheet.get_all_records()
        except: pass
        ko_df_all = pd.DataFrame(all_ko_picks)
        
        try:
            sheet = connect_to_sheet()
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                rename_dict = {df.columns[0]: 'Timestamp', df.columns[1]: 'Name'}
                for col in df.columns:
                    clean_col = re.sub(r'\s+', '', str(col)).upper()
                    if re.match(r'^([A-L][1-4])$', clean_col): rename_dict[col] = clean_col
                    elif clean_col == 'STATUS': rename_dict[col] = 'Status'
                df = df.rename(columns=rename_dict)
                if 'Status' not in df.columns: df['Status'] = 'Pending'

                paid_count = df['Status'].astype(str).str.strip().str.lower().eq('paid').sum()
                st.sidebar.metric(label="💰 Total Pool Pot", value=f"${paid_count * 10} USD")

                def calculate_live_user_score(row):
                    total_points = 0
                    group_mapping = {chr(65+i): f"Group {chr(65+i)}" for i in range(12)}
                    for letter, group_key in group_mapping.items():
                        current_live_order = live_standings_map.get(group_key, [])
                        if not current_live_order or len(current_live_order) < 4: continue
                        for pos in range(1, 5):
                            p1 = CLEAN_TEAM_MAP.get(standardize_string(row.get(f"{letter}{pos}", "")), "")
                            if p1 == current_live_order[pos-1]: total_points += 1
                                    
                    if not ko_df_all.empty and live_matches_list:
                        u_name = str(row.get('Name')).strip().lower()
                        user_subset = ko_df_all[ko_df_all['Name'].astype(str).str.lower() == u_name]
                        for _, ko_pick in user_subset.iterrows():
                            match_id_target = str(ko_pick.get('Match_ID'))
                            api_match = next((m for m in live_matches_list if str(m.get('id')) == match_id_target), None)
                            if api_match and api_match.get('status') == 'FINISHED':
                                api_ft = api_match.get('score', {}).get('fullTime', {})
                                if str(ko_pick.get('Home_Score')) == str(api_ft.get('home')): total_points += 1
                                if str(ko_pick.get('Away_Score')) == str(api_ft.get('away')): total_points += 1
                                act_winner_side = api_match.get('score', {}).get('winner')
                                act_winner_name = ""
                                if act_winner_side == "HOME_TEAM": act_winner_name = api_match.get('homeTeam', {}).get('name')
                                elif act_winner_side == "AWAY_TEAM": act_winner_name = api_match.get('awayTeam', {}).get('name')
                                if act_winner_name and str(ko_pick.get('Winner')).strip().lower() == CLEAN_TEAM_MAP.get(standardize_string(act_winner_name), act_winner_name).strip().lower():
                                    total_points += 1
                    return total_points

                df['Points'] = df.apply(calculate_live_user_score, axis=1)
                leaderboard_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
                
                st.subheader("Current Leaderboard Matrix")
                cols = st.columns([2, 1, 1, 2])
                cols[0].markdown("**Name**"); cols[1].markdown("**Points**"); cols[2].markdown("**Status**"); cols[3].markdown("**Download**")
                st.divider()
                for _, r in leaderboard_df.iterrows():
                    cols = st.columns([2, 1, 1, 2])
                    cols[0].write(r['Name']); cols[1].write(r['Points']); cols[2].write(r['Status'])
                    csv = df[df['Name'] == r['Name']].to_csv(index=False).encode('utf-8')
                    cols[3].download_button(label="📥 CSV", data=csv, file_name=f"{r['Name']}_picks.csv", key=f"dl_{r['Name']}")
            else: st.info("No entries found yet.")
        except Exception as e: st.error(f"Leaderboard logic error: {e}")

# --- PAGE 3: LOCKED GROUP INSTRUCTIONS ---
elif page == "Group Predictions (Closed)":
    st.title("🏆 Group Phase Standings Matrix")
    st.warning("🔒 Group phase prediction window is closed.")

# --- PAGE 4: RULES & FORUM ---
elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules")
    with st.expander("View Details", expanded=True):
        st.write("**Scoring Formula:** Group match order accuracy = 1 point per team placement. Knockout phase accuracy = 1 point for the correct match outcome (advancing team) + 1 point for each exact individual team score prediction.")
        st.info("USA: Venmo @jhradecky | Canada: Interac e-transfer julien.hradecky@gmail.com")
