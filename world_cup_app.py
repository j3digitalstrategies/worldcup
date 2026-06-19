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
                if team not in ordered_teams:
                    ordered_teams.append(team)
                    
            if len(ordered_teams) >= 4:
                updated_map[clean_group_key] = ordered_teams[:4]
                
    if len(updated_map) == 0:
        raise Exception("No matching groups parsed from API response")
        
    return updated_map

# --- APP UI SETUP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation", ["Leaderboard", "Make Predictions", "Rules & Chat Forum"])

with st.sidebar:
    st.header("Player Info")
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

# --- PAGE 1: LEADERBOARD ---
if page == "Leaderboard":
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

# --- PAGE 2: PREDICTIONS ---
elif page == "Make Predictions":
    st.title("🏆 2026 World Cup Predictions")
    st.info("Rank teams 1-4. Real-time points are awarded based on active live standings!")
    
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
                sheet.append_row([timestamp, user_name] + all_picks + ["Pending"])
                st.success("Predictions Saved!")
                
                df_user = pd.DataFrame(summary_data)
                csv = df_user.to_csv(index=False).encode('utf-8')
                st.download_button(label="Download My Picks (.csv)", data=csv, file_name=f"{user_name}_WC2026_Picks.csv", mime="text/csv")
                st.balloons()
            except Exception as e:
                st.error(f"Error saving to Google Sheets: {e}")

# --- PAGE 3: RULES & CHAT FORUM ---
elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules & Payment")
    with st.expander("View Full Rules & Payment Details", expanded=True):
        st.warning("⚠️ **Deadline:** All picks must be submitted before June 11, 2026.")
        st.write("**Scoring System:** Each correct position pick = 1 point.")
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
