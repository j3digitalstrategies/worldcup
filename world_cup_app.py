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

def standardize_string(val):
    if val is None:
        return ""
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
            # Auto-create knockout predictions sheet with correct headers if missing
            new_tab = spreadsheet.add_worksheet(title="Knockout_Picks", rows="1000", cols="7")
            new_tab.append_row(["Timestamp", "Name", "Match_ID", "Home_Score", "Away_Score", "Winner", "Stage"])
            return new_tab
            
    if tab_name == "sheet1":
        return spreadsheet.sheet1
    return spreadsheet.worksheet(tab_name)

if "automated_live_cache" not in st.session_state:
    st.session_state["automated_live_cache"] = INITIAL_SEED_STANDINGS
if "cache_status_msg" not in st.session_state:
    st.session_state["cache_status_msg"] = "🔄 Initializing data pipeline..."

@st.cache_data(ttl=10800)
def fetch_and_merge_api_data():
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(f"{BASE_URL}?season=2026", headers=headers, timeout=12)
    
    if response.status_code != 200:
        raise Exception(f"HTTP Error {response.status_code}: {response.text}")
        
    data = response.json()
    if 'standings' not in data or len(data['standings']) == 0:
        raise Exception("Invalid or empty data payload from API")
        
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
        
        if not clean_group_key or clean_group_key not in INITIAL_SEED_STANDINGS:
            for row in block.get('table', []):
                team_node = row.get('team', {})
                raw_name = team_node.get('shortName') or team_node.get('name')
                if raw_name:
                    lookup = standardize_string(raw_name)
                    clean_name = CLEAN_TEAM_MAP.get(lookup, str(raw_name).strip())
                    
                    for g_key, g_teams in groups.items():
                        if clean_name in g_teams:
                            clean_group_key = g_key
                            break
                if clean_group_key:
                    break
                    
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
                if team not in ordered_teams:
                    ordered_teams.append(team)
                    
            if len(ordered_teams) >= 4:
                updated_map[clean_group_key] = ordered_teams[:4]
                
    if len(updated_map) == 0:
        raise Exception("No matching groups could be identified or parsed from the server response data structure.")
        
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

# --- FETCH REGISTERED USER LIST FOR DROPDOWN ---
def get_registered_players():
    try:
        sheet = connect_to_sheet("sheet1")
        records = sheet.get_all_records()
        if records:
            df = pd.DataFrame(records)
            if len(df.columns) >= 2:
                name_col = df.columns[1]
                return sorted(list(df[name_col].astype(str).str.strip().unique()))
    except:
        pass
    return []

registered_players = get_registered_players()

# --- APP UI SETUP ---
page = st.sidebar.radio("Navigation", ["Knockout Predictions", "Leaderboard", "Group Stage Predictions (Closed)", "Rules & Chat Forum"])

with st.sidebar:
    st.header("Player Info")
    
    # Combined Dropdown + Text fallback solution for finding names dynamically
    if registered_players:
        selected_dropdown_name = st.selectbox("Select Your Name:", ["-- Select Existing Player --"] + registered_players)
        if selected_dropdown_name != "-- Select Existing Player --":
            user_name = selected_dropdown_name
        else:
            user_name = st.text_input("Or Type Full Name:")
    else:
        user_name = st.text_input("Full Name:")
        
    st.divider()
    st.markdown("### 📸 Official Instagram")
    st.write("Make sure you follow the official instagram **@2026fifawcp** for updates.")
    try:
        st.image("qr-code.png", caption="Scan to follow", use_container_width=True)
    except:
        st.caption("(QR Code image file missing)")
        
    st.divider()
    if st.button("🔄 Force Refresh Cache", use_container_width=True):
        st.cache_data.clear()
        if "api_error_details" in st.session_state:
            del st.session_state["api_error_details"]
        st.rerun()

# --- PAGE 1: KNOCKOUT PREDICTIONS ---
if page == "Knockout Predictions":
    st.title("🏆 Knockout Round Predictions")
    st.markdown("As matchups are finalized by live match schedules, enter your scores below. You can log back in anytime to update entries before games kickoff.")
    
    if not user_name or user_name.strip() == "":
        st.warning("👈 Please select or enter your Full Name in the sidebar to view or edit knockout picks.")
    else:
        st.success(f"Active Session Profile: **{user_name}**")
        
        # Load existing choices from Google Sheets
        ko_records = []
        try:
            ko_sheet = connect_to_sheet("Knockout_Picks")
            ko_records = ko_sheet.get_all_records()
        except Exception as e:
            st.error(f"Could not connect to Knockout Sheets database: {e}")
            
        user_ko_df = pd.DataFrame(ko_records)
        if not user_ko_df.empty:
            user_ko_df = user_ko_df[user_ko_df['Name'].astype(str).str.lower() == user_name.strip().lower()]

        # Pull match schedules
        raw_matches = fetch_live_matches_api()
        knockout_stages = ["ROUND_OF_32", "ROUND_OF_16", "QUARTER_FINALS", "SEMI_FINALS", "FINAL"]
        
        # Filter matches where actual opponents are confirmed
        active_fixtures = []
        for m in raw_matches:
            if m.get('stage') in knockout_stages:
                h_team = m.get('homeTeam', {}).get('name')
                a_team = m.get('awayTeam', {}).get('name')
                if h_team and a_team:
                    active_fixtures.append(m)

        # Fallback simulation fixtures if API doesn't contain active knockout stages yet
        if not active_fixtures:
            st.info("💡 Waiting on confirmed match calculations from the live API feed. Displaying upcoming scheduled openers for preview testing:")
            active_fixtures = [
                {"id": 7301, "stage": "ROUND_OF_32", "status": "TIMED", "homeTeam": {"name": "Germany"}, "awayTeam": {"name": "Ecuador"}},
                {"id": 7302, "stage": "ROUND_OF_32", "status": "TIMED", "homeTeam": {"name": "South Korea"}, "awayTeam": {"name": "Canada"}},
                {"id": 7303, "stage": "ROUND_OF_32", "status": "TIMED", "homeTeam": {"name": "Mexico"}, "awayTeam": {"name": "Bosnia"}},
            ]

        # Group fixtures cleanly by tournament tier
        for stage_group in knockout_stages:
            stage_matches = [m for m in active_fixtures if m.get('stage') == stage_group]
            if not stage_matches:
                continue
                
            st.markdown(f"### 📦 {stage_group.replace('_', ' ')}")
            
            for m in stage_matches:
                m_id = str(m.get('id'))
                h_name = m.get('homeTeam', {}).get('name')
                a_name = m.get('awayTeam', {}).get('name')
                is_locked = m.get('status') not in ["TIMED", "SCHEDULED"]
                
                # Fetch clean structural names via mapped standardization dictionaries
                lookup_h = standardize_string(h_name)
                lookup_a = standardize_string(a_name)
                clean_h = CLEAN_TEAM_MAP.get(lookup_h, h_name)
                clean_a = CLEAN_TEAM_MAP.get(lookup_a, a_name)
                
                # Retrieve saved historic data records if matching values exist
                exist_row = user_ko_df[user_ko_df['Match_ID'].astype(str) == m_id] if not user_ko_df.empty else pd.DataFrame()
                
                default_h_score = int(exist_row['Home_Score'].values[0]) if not exist_row.empty else 0
                default_a_score = int(exist_row['Away_Score'].values[0]) if not exist_row.empty else 0
                default_winner = str(exist_row['Winner'].values[0]) if not exist_row.empty else clean_h
                
                # Visual box module layout
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 3])
                    
                    with c1:
                        st.markdown(f"#### {clean_h}")
                        h_score = st.number_input("Score", min_value=0, max_value=20, value=default_h_score, key=f"h_{m_id}", disabled=is_locked)
                    
                    with c2:
                        st.markdown("<h3 style='text-align: center; margin-top: 25px;'>VS</h3>", unsafe_allow_html=True)
                        
                    with c3:
                        st.markdown(f"#### {clean_a}")
                        a_score = st.number_input("Score", min_value=0, max_value=20, value=default_a_score, key=f"a_{m_id}", disabled=is_locked)
                    
                    with c4:
                        st.markdown("#### Outcome Target")
                        if h_score == a_score:
                            winner_choices = [clean_h, clean_a]
                            def_idx = winner_choices.index(default_winner) if default_winner in winner_choices else 0
                            final_winner = st.selectbox("Advances via PKs", options=winner_choices, index=def_idx, key=f"w_{m_id}", disabled=is_locked)
                        else:
                            final_winner = clean_h if h_score > a_score else clean_a
                            st.info(f"👉 Winner: {final_winner}")
                    
                    # Individual item persistence router updates
                    if not is_locked:
                        if st.button("Save Prediction Entry", key=f"btn_{m_id}"):
                            try:
                                ko_sheet = connect_to_sheet("Knockout_Picks")
                                full_ko_records = ko_sheet.get_all_records()
                                
                                target_row_idx = -1
                                for idx, r in enumerate(full_ko_records):
                                    if str(r.get('Name')).strip().lower() == user_name.strip().lower() and str(r.get('Match_ID')) == m_id:
                                        target_row_idx = idx + 2
                                        break
                                
                                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                new_row = [timestamp, user_name.strip(), m_id, int(h_score), int(a_score), final_winner, stage_group]
                                
                                if target_row_idx != -1:
                                    ko_sheet.update(range_name=f"A{target_row_idx}:G{target_row_idx}", values=[new_row])
                                else:
                                    ko_sheet.append_row(new_row)
                                    
                                st.toast(f"Saved: {clean_h} vs {clean_a} choice captured!", icon="✅")
                            except Exception as ex:
                                st.error(f"Error parsing connection parameters: {ex}")
                    else:
                        st.caption("🔒 Match has commenced. Entry options frozen.")

# --- PAGE 2: LEADERBOARD ---
elif page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    with st.spinner("Calculating live scores..."):
        try:
            api_data = fetch_and_merge_api_data()
            current_memory = dict(st.session_state["automated_live_cache"])
            current_memory.update(api_data)
            st.session_state["automated_live_cache"] = current_memory
            st.session_state["cache_status_msg"] = f"✅ Fully Automated: Sync accurate as of {datetime.now().strftime('%H:%M')}"
            is_using_memory_fallback = False
            if "api_error_details" in st.session_state:
                del st.session_state["api_error_details"]
        except Exception as api_err:
            st.session_state["cache_status_msg"] = "📡 API connection delayed. Utilizing last known saved live standings."
            st.session_state["api_error_details"] = str(api_err)
            is_using_memory_fallback = True
            
        live_standings_map = st.session_state["automated_live_cache"]
        
        # Load match data calculations for knockout scores
        live_matches_list = fetch_live_matches_api()
        
        all_ko_picks = []
        try:
            ko_sheet = connect_to_sheet("Knockout_Picks")
            all_ko_picks = ko_sheet.get_all_records()
        except:
            pass
        ko_df_all = pd.DataFrame(all_ko_picks)
        
        try:
            sheet = connect_to_sheet()
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                
                rename_dict = {}
                if len(df.columns) >= 2:
                    rename_dict[df.columns[0]] = 'Timestamp'
                    rename_dict[df.columns[1]] = 'Name'
                
                for col in df.columns:
                    clean_col = re.sub(r'\s+', '', str(col)).upper()
                    match = re.match(r'^([A-L][1-4])$', clean_col)
                    if match:
                        rename_dict[col] = match.group(1)
                    elif clean_col == 'STATUS':
                        rename_dict[col] = 'Status'
                
                df = df.rename(columns=rename_dict)
                if 'Status' not in df.columns:
                    df['Status'] = 'Pending'

                paid_count = df['Status'].astype(str).str.strip().str.lower().eq('paid').sum()
                total_pot = paid_count * 10

                metric_col1, metric_col2 = st.columns([3, 1])
                with metric_col1:
                    if is_using_memory_fallback:
                        st.info(st.session_state["cache_status_msg"])
                        if "api_error_details" in st.session_state:
                            st.error(f"❌ Raw Server Response: {st.session_state['api_error_details']}")
                    else:
                        st.success(st.session_state["cache_status_msg"])
                with metric_col2:
                    st.metric(label="💰 Total Pool Pot", value=f"${total_pot} USD")
                
                st.divider()

                def calculate_live_user_score(row):
                    if not live_standings_map:
                        return 0
                    total_points = 0
                    
                    # 1. Calculate Group Points
                    group_mapping = {
                        'A': 'Group A', 'B': 'Group B', 'C': 'Group C', 'D': 'Group D',
                        'E': 'Group E', 'F': 'Group F', 'G': 'Group G', 'H': 'Group H',
                        'I': 'Group I', 'J': 'Group J', 'K': 'Group K', 'L': 'Group L'
                    }
                    
                    for letter, group_key in group_mapping.items():
                        current_live_order = live_standings_map.get(group_key, [])
                        if not current_live_order or len(current_live_order) < 4:
                            continue
                            
                        p1 = CLEAN_TEAM_MAP.get(standardize_string(row.get(f"{letter}1", "")), "")
                        p2 = CLEAN_TEAM_MAP.get(standardize_string(row.get(f"{letter}2", "")), "")
                        p3 = CLEAN_TEAM_MAP.get(standardize_string(row.get(f"{letter}3", "")), "")
                        p4 = CLEAN_TEAM_MAP.get(standardize_string(row.get(f"{letter}4", "")), "")
                        
                        if p1 == current_live_order[0]: total_points += 1
                        if p2 == current_live_order[1]: total_points += 1
                        if p3 == current_live_order[2]: total_points += 1
                        if p4 == current_live_order[3]: total_points += 1
                    
                    # 2. Add Mapped Knockout Matrix Points
                    if not ko_df_all.empty and live_matches_list:
                        u_name = str(row.get('Name')).strip().lower()
                        user_subset = ko_df_all[ko_df_all['Name'].astype(str).str.lower() == u_name]
                        
                        for _, ko_pick in user_subset.iterrows():
                            match_id_target = str(ko_pick.get('Match_ID'))
                            api_match = next((m for m in live_matches_list if str(m.get('id')) == match_id_target), None)
                            
                            if api_match and api_match.get('status') == 'FINISHED':
                                api_score = api_match.get('score', {})
                                api_ft = api_score.get('fullTime', {})
                                
                                act_h = api_ft.get('home')
                                act_a = api_ft.get('away')
                                act_winner_side = api_score.get('winner') # HOME_TEAM, AWAY_TEAM
                                
                                pred_h = ko_pick.get('Home_Score')
                                pred_a = ko_pick.get('Away_Score')
                                pred_winner = str(ko_pick.get('Winner')).strip().lower()
                                
                                # Micro accuracy checks
                                if str(pred_h) == str(act_h): total_points += 1
                                if str(pred_a) == str(act_a): total_points += 1
                                
                                # Direct winner match validation checks
                                act_winner_name = ""
                                if act_winner_side == "HOME_TEAM":
                                    act_winner_name = api_match.get('homeTeam', {}).get('name')
                                elif act_winner_side == "AWAY_TEAM":
                                    act_winner_name = api_match.get('awayTeam', {}).get('name')
                                    
                                if act_winner_name:
                                    clean_act_winner = CLEAN_TEAM_MAP.get(standardize_string(act_winner_name), act_winner_name).strip().lower()
                                    if pred_winner == clean_act_winner:
                                        total_points += 1
                                        
                    return total_points

                df['Points'] = df.apply(calculate_live_user_score, axis=1)
                leaderboard_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
                
                st.subheader("Current Standings")
                header_cols = st.columns([2, 1, 1, 2])
                header_cols[0].markdown("**Name**")
                header_cols[1].markdown("**Points**")
                header_cols[2].markdown("**Status**")
                header_cols[3].markdown("**Download**")
                st.divider()
                
                for _, row in leaderboard_df.iterrows():
                    cols = st.columns([2, 1, 1, 2])
                    cols[0].write(row['Name'])
                    cols[1].write(row['Points'])
                    cols[2].write(row['Status'])
                    
                    user_row_df = df[df['Name'] == row['Name']]
                    csv = user_row_df.to_csv(index=False).encode('utf-8')
                    cols[3].download_button(
                        label="📥 CSV", 
                        data=csv, 
                        file_name=f"{row['Name']}_picks.csv", 
                        key=f"dl_{row['Name']}_{row['Points']}"
                    )
                
                with st.expander("🛠️ Diagnostics View"):
                    st.write("#### Live Standings Memory Map:")
                    st.json(live_standings_map)
            else:
                st.info("No entries yet.")
        except Exception as e:
            st.error(f"Leaderboard Error: {e}")

# --- PAGE 3: GROUP STAGE PREDICTIONS (CLOSED) ---
elif page == "Group Stage Predictions (Closed)":
    st.title("🏆 Group Stage Predictions")
    st.warning("🔒 The selection window for group pairings is closed. Existing points tracking datasets have locked to secure ongoing pool mechanics.")

# --- PAGE 4: RULES & CHAT FORUM ---
elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules & Payment")
    with st.expander("View Full Rules & Payment Details", expanded=True):
        st.warning("⚠️ **Deadline:** All picks must be submitted before June 11, 2026.")
        st.write("**Scoring System:** Each correct position pick = 1 point.")
        st.write("**Knockout Rounds:** 1 point for the correct match outcome (including penalty results) + 1 point for each exact individual team score prediction.")
        st.write("**Entry Fee:** $10 USD / $15 CAD / £7.50 GBP")
        st.info("**USA:** Venmo @jhradecky  \n**Canada:** E-transfer julien.hradecky@gmail.com")
        st.write("**Prizes:** 1st: 70% | 2nd: 20% | 3rd: Refund")

    st.divider()
    st.header("💬 Chat Forum")
    with st.form("chat_form", clear_on_submit=True):
        comment = st.text_area("Share a question or talk some trash:")
        submitted = st.form_submit_button("Post Message")
        if submitted:
            if not user_name:
                st.error("Please enter your name in the sidebar.")
            elif not comment:
                st.error("Message cannot be empty.")
            else:
                try:
                    chat_sheet = connect_to_sheet("Chat_Data")
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    chat_sheet.append_row([now, user_name, comment])
                    st.success("Message posted!")
                except:
                    st.error("Could not post message.")

    try:
        chat_sheet = connect_to_sheet("Chat_Data")
        messages = chat_sheet.get_all_records()
        if messages:
            for msg in reversed(messages[-15:]):
                st.markdown(f"**{msg['User']}** ({msg['Timestamp']})")
                st.write(msg['Message'])
                st.divider()
    except:
        st.warning("Chat history is currently unavailable.")
