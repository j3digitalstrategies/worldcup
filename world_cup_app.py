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
MATCHES_URL = "https://api.football-data.org/v4/competitions/WC/matches"

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

# --- HARDCODED SEED STANDINGS ---
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

# --- UNIVERSAL CLEANER MAP ---
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

# --- CHRONOLOGICAL KNOCKOUT OVERRIDES ---
# Maps placeholder entries to your verified schedule until the API database locks them in.
KNOWN_R32_FALLBACKS = [
    ("South Africa", "Canada"),        # 1. Sun, 28 Jun, 21:00
    ("Brazil", "Japan"),               # 2. Mon, 29 Jun, 19:00
    ("Germany", "TBD"),                # 3. Mon, 29 Jun, 22:30
    ("Netherlands", "Morocco"),        # 4. Tue, 30 Jun, 03:00
    ("Côte d'Ivoire", "TBD"),          # 5. Tue, 30 Jun, 19:00
    ("TBD", "TBD"),                    # 6. Tue, 30 Jun, 23:00
    ("Mexico", "TBD"),                 # 7. Wed, 1 Jul, 03:00
    ("TBD", "TBD"),                    # 8. Wed, 1 Jul, 18:00
    ("TBD", "TBD"),                    # 9. Wed, 1 Jul, 22:00
    ("USA", "Bosnia and Herzegovina"), # 10. Thu, 2 Jul, 02:00
    ("TBD", "TBD"),                    # 11. Thu, 2 Jul, 21:00
    ("TBD", "TBD"),                    # 12. Fri, 3 Jul, 01:00
    ("Switzerland", "TBD"),            # 13. Fri, 3 Jul, 05:00
    ("Australia", "TBD"),              # 14. Fri, 3 Jul, 20:00
    ("Argentina", "TBD"),              # 15. Sat, 4 Jul, 00:00
    ("TBD", "TBD")                     # 16. Sat, 4 Jul, 03:30
]

def standardize_string(val):
    if val is None:
        return ""
    cleaned = re.sub(r'[\s\xa0\u200b\u200c\u200d]+', '', str(val))
    return cleaned.lower().replace("-", "").replace("_", "").replace(".", "")

def get_resolved_team_name(team_node, stage, match_index, side):
    """Resolves names using real data first, our fallbacks second, and placeholders last."""
    if not team_node:
        raw_name = ""
    else:
        raw_name = team_node.get('name') or team_node.get('shortName') or ""
        
    lookup = standardize_string(raw_name)
    
    # Identify if the API is using a placeholder string
    is_placeholder = any(x in raw_name.lower() for x in ["winner", "runner-up", "to be", "tbd", "placeholder", "best 3rd"]) or raw_name == ""
    
    # If the API returns a real team country name, immediately let it take priority
    if not is_placeholder:
        return CLEAN_TEAM_MAP.get(lookup, raw_name)
        
    # If it is a placeholder, use our verified fallback track
    if stage == "ROUND_OF_32" and 0 <= match_index < len(KNOWN_R32_FALLBACKS):
        pair = KNOWN_R32_FALLBACKS[match_index]
        return pair[0] if side == 'home' else pair[1]
        
    return raw_name if raw_name else "TBD"

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
            
    if tab_name == "sheet1":
        return spreadsheet.sheet1
    return spreadsheet.worksheet(tab_name)

if "automated_live_cache" not in st.session_state:
    st.session_state["automated_live_cache"] = INITIAL_SEED_STANDINGS

@st.cache_data(ttl=10800)
def fetch_and_merge_api_data():
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(f"{BASE_URL}?season=2026", headers=headers, timeout=12)
    if response.status_code != 200:
        raise Exception(f"HTTP Error {response.status_code}: {response.text}")
    data = response.json()
    updated_map = {}
    for block in data['standings']:
        clean_group_key = None
        raw_group_name = block.get('group')
        if raw_group_name:
            group_str = str(raw_group_name).upper()
            match = re.search(r'\b([A-L])\b|GROUP[\s_-]*([A-L])', group_str)
            if match:
                letter = match.group(1) or match.group(2)
                clean_group_key = f"Group {letter}"
        if clean_group_key in INITIAL_SEED_STANDINGS:
            ordered_teams = []
            for row in block.get('table', []):
                team_node = row.get('team', {})
                raw_name = team_node.get('shortName') or team_node.get('name')
                if raw_name:
                    ordered_teams.append(CLEAN_TEAM_MAP.get(standardize_string(raw_name), raw_name))
            for team in INITIAL_SEED_STANDINGS[clean_group_key]:
                if team not in ordered_teams: ordered_teams.append(team)
            if len(ordered_teams) >= 4:
                updated_map[clean_group_key] = ordered_teams[:4]
    return updated_map

@st.cache_data(ttl=1800)
def fetch_live_matches_api():
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{MATCHES_URL}?season=2026", headers=headers, timeout=12)
        if response.status_code == 200:
            return response.json().get('matches', [])
    except:
        pass
    return []

def get_registered_players():
    try:
        sheet = connect_to_sheet("sheet1")
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            if len(df.columns) >= 2:
                return sorted(list(df[df.columns[1]].astype(str).str.strip().unique()))
    except:
        pass
    return []

# --- APP SETUP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation", ["Knockout Predictions", "Leaderboard", "Group Predictions (Closed)", "Rules & Chat Forum"])
registered_players = get_registered_players()

with st.sidebar:
    st.header("Player Info")
    if registered_players:
        selected_dropdown_name = st.selectbox("Select Your Name:", ["-- Select Existing Player --"] + registered_players)
        user_name = selected_dropdown_name if selected_dropdown_name != "-- Select Existing Player --" else ""
    else:
        st.warning("⚠️ No registered players found.")
        user_name = ""
    st.divider()
    if st.button("🔄 Force Refresh Cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- PAGE 1: KNOCKOUT PREDICTIONS ---
if page == "Knockout Predictions":
    st.title("🏆 Knockout Round Predictions Portal")
    st.markdown("Your previous selections are safely saved. Adjust scores below dynamically until kickoff time.")
    
    if not user_name:
        st.warning("👈 Please select your Name from the sidebar dropdown menu to view or edit knockout picks.")
    else:
        st.success(f"Active Profile: **{user_name}**")
        
        ko_records = []
        try:
            ko_sheet = connect_to_sheet("Knockout_Picks")
            ko_records = ko_sheet.get_all_records()
        except:
            pass
            
        user_ko_df = pd.DataFrame(ko_records)
        if not user_ko_df.empty:
            user_ko_df = user_ko_df[user_ko_df['Name'].astype(str).str.lower() == user_name.strip().lower()]

        raw_matches = fetch_live_matches_api()
        knockout_stages = ["ROUND_OF_32", "ROUND_OF_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]
        active_fixtures = [m for m in raw_matches if m.get('stage') in knockout_stages]

        # Secure chronological baseline sorting
        if not active_fixtures:
            # Generate temporary structure if API is empty
            active_fixtures = [{"id": 100 + i, "stage": "ROUND_OF_32", "status": "SCHEDULED", "utcDate": f"2026-06-28T{i}:00:00Z"} for i in range(16)]

        for stage_group in knockout_stages:
            stage_matches = [m for m in active_fixtures if m.get('stage') == stage_group]
            if not stage_matches: continue
            
            # Critical sorting rule step: arrange strictly by kickoff time alignment
            stage_matches = sorted(stage_matches, key=lambda x: x.get('utcDate', ''))
            
            st.markdown(f"### 📦 {stage_group.replace('_', ' ')}")
            
            for idx, m in enumerate(stage_matches):
                m_id = str(m.get('id'))
                is_locked = m.get('status') not in ["TIMED", "SCHEDULED"]
                
                # Fetch verified dynamic strings
                clean_h = get_resolved_team_name(m.get('homeTeam'), stage_group, idx, 'home')
                clean_a = get_resolved_team_name(m.get('awayTeam'), stage_group, idx, 'away')
                
                exist_row = user_ko_df[user_ko_df['Match_ID'].astype(str) == m_id] if not user_ko_df.empty else pd.DataFrame()
                default_h_score = int(exist_row['Home_Score'].values[0]) if not exist_row.empty else 0
                default_a_score = int(exist_row['Away_Score'].values[0]) if not exist_row.empty else 0
                default_winner = str(exist_row['Winner'].values[0]) if not exist_row.empty else clean_h
                
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1, 3, 3])
                    with c1:
                        st.markdown(f"#### {clean_h}")
                        h_score = st.number_input("Goals", min_value=0, max_value=20, value=default_h_score, key=f"h_{m_id}_{stage_group}", disabled=is_locked)
                    with c2:
                        st.markdown("<h3 style='text-align: center; padding-top: 25px;'>VS</h3>", unsafe_allow_html=True)
                    with c3:
                        st.markdown(f"#### {clean_a}")
                        a_score = st.number_input("Goals", min_value=0, max_value=20, value=default_a_score, key=f"a_{m_id}_{stage_group}", disabled=is_locked)
                    with c4:
                        st.markdown("#### Outcome Target")
                        if h_score == a_score:
                            winner_choices = [clean_h, clean_a]
                            def_idx = winner_choices.index(default_winner) if default_winner in winner_choices else 0
                            final_winner = st.selectbox("Advances via PKs", options=winner_choices, index=def_idx, key=f"w_{m_id}_{stage_group}", disabled=is_locked)
                        else:
                            final_winner = clean_h if h_score > a_score else clean_a
                            st.info(f"👉 Winner: {final_winner}")
                    
                    if not is_locked:
                        if st.button("Save Prediction Entry", key=f"btn_{m_id}_{stage_group}"):
                            try:
                                ko_sheet = connect_to_sheet("Knockout_Picks")
                                full_ko_records = ko_sheet.get_all_records()
                                target_row_idx = -1
                                for row_i, r in enumerate(full_ko_records):
                                    if str(r.get('Name')).strip().lower() == user_name.strip().lower() and str(r.get('Match_ID')) == m_id:
                                        target_row_idx = row_i + 2
                                        break
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                new_row = [timestamp, user_name.strip(), m_id, int(h_score), int(a_score), final_winner, stage_group]
                                if target_row_idx != -1:
                                    ko_sheet.update(range_name=f"A{target_row_idx}:G{target_row_idx}", values=[new_row])
                                else:
                                    ko_sheet.append_row(new_row)
                                st.toast(f"Saved: {clean_h} vs {clean_a} choice logged!", icon="✅")
                            except Exception as ex:
                                st.error(f"Error writing to sheet: {ex}")

# --- PAGE 2: LEADERBOARD ---
elif page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    with st.spinner("Calculating live scores..."):
        try:
            live_standings_map = fetch_and_merge_api_data()
            st.success("✅ Fully Automated Standings Synced")
        except:
            live_standings_map = st.session_state["automated_live_cache"]
            st.info("📡 Using cached standings data.")
            
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
                    match = re.match(r'^([A-L][1-4])$', clean_col)
                    if match: rename_dict[col] = match.group(1)
                    elif clean_col == 'STATUS': rename_dict[col] = 'Status'
                df = df.rename(columns=rename_dict)
                if 'Status' not in df.columns: df['Status'] = 'Pending'

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
                        
                        # Apply chronological sorting to align accurate indexing criteria
                        for stage_group in ["ROUND_OF_32", "ROUND_OF_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]:
                            stage_api_matches = sorted([m for m in live_matches_list if m.get('stage') == stage_group], key=lambda x: x.get('utcDate', ''))
                            
                            for idx, api_match in enumerate(stage_api_matches):
                                match_id_target = str(api_match.get('id'))
                                ko_pick = user_subset[user_subset['Match_ID'].astype(str) == match_id_target]
                                if ko_pick.empty: continue
                                ko_pick = ko_pick.iloc[0]
                                
                                if api_match.get('status') == 'FINISHED':
                                    api_ft = api_match.get('score', {}).get('fullTime', {})
                                    if str(ko_pick.get('Home_Score')) == str(api_ft.get('home')): total_points += 1
                                    if str(ko_pick.get('Away_Score')) == str(api_ft.get('away')): total_points += 1
                                    
                                    act_winner_side = api_match.get('score', {}).get('winner')
                                    act_winner_name = ""
                                    if act_winner_side == "HOME_TEAM": act_winner_name = api_match.get('homeTeam', {}).get('name')
                                    elif act_winner_side == "AWAY_TEAM": act_winner_name = api_match.get('awayTeam', {}).get('name')
                                    
                                    if act_winner_name:
                                        clean_act_winner = CLEAN_TEAM_MAP.get(standardize_string(act_winner_name), act_winner_name).strip().lower()
                                        if str(ko_pick.get('Winner')).strip().lower() == clean_act_winner: total_points += 1
                    return total_points

                df['Points'] = df.apply(calculate_live_user_score, axis=1)
                leaderboard_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
                
                st.subheader("Current Standings")
                cols = st.columns([2, 1, 1, 2])
                cols[0].markdown("**Name**"); cols[1].markdown("**Points**"); cols[2].markdown("**Status**"); cols[3].markdown("**Download**")
                st.divider()
                for _, r in leaderboard_df.iterrows():
                    cols = st.columns([2, 1, 1, 2])
                    cols[0].write(r['Name']); cols[1].write(r['Points']); cols[2].write(r['Status'])
                    csv = df[df['Name'] == r['Name']].to_csv(index=False).encode('utf-8')
                    cols[3].download_button(label="📥 CSV", data=csv, file_name=f"{r['Name']}_picks.csv", key=f"dl_{r['Name']}")
            else: st.info("No entries yet.")
        except Exception as e: st.error(f"Leaderboard Error: {e}")

# --- PAGE 3: CLOSED GROUP INSTRUCTIONS ---
elif page == "Group Predictions (Closed)":
    st.title("🏆 Group Predictions Locked")
    st.warning("🔒 Group phase prediction window is closed.")

# --- PAGE 4: RULES & CHAT FORUM ---
elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules")
    with st.expander("View Full Rules & Payment Details", expanded=True):
        st.write("**Scoring Formula:** Group match order accuracy = 1 point per team placement. Knockout phase accuracy = 1 point for the correct match outcome (advancing team) + 1 point for each exact individual team score prediction.")
        st.info("**USA:** Venmo @jhradecky  \n**Canada:** E-transfer julien.hradecky@gmail.com")
