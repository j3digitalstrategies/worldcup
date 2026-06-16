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

# --- MANUAL LIVE STANDINGS OVERRIDE (HARD FAIL-SAFE) ---
MANUAL_LIVE_STANDINGS = {
    "Group A": ["Mexico", "South Korea", "South Africa", "Czechia"],
    "Group B": ["Switzerland", "Canada", "Bosnia", "Qatar"],
    "Group C": ["Brazil", "Morocco", "Scotland", "Haiti"],
    "Group D": ["USA", "Türkiye", "Australia", "Paraguay"],
    "Group E": ["Germany", "Ivory Coast", "Ecuador", "Curaçao"],
    "Group F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "Group G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "Group H": ["Spain", "Uruguay", "Saudi Arabia", "Cape Verde"],
    "Group I": ["France", "Norway", "Senegal", "Iraq"],
    "Group J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "Group K": ["Portugal", "Colombia", "Uzbekistan", "DR Congo"],
    "Group L": ["England", "Croatia", "Ghana", "Panama"]
}

# --- UNIVERSAL CLEANER MAP ---
CLEAN_TEAM_MAP = {
    "mexico": "Mexico", "southafrica": "South Africa", "southkorea": "South Korea",
    "korearepublic": "South Korea", "czechia": "Czechia", "czechrepublic": "Czechia",
    "canada": "Canada", "switzerland": "Switzerland", "qatar": "Qatar",
    "bosnia": "Bosnia", "bosniaandherzegovina": "Bosnia", "bosniaherzegovina": "Bosnia",
    "bosniah": "Bosnia", "brazil": "Brazil", "morocco": "Morocco", "haiti": "Haiti",
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
    if not val:
        return ""
    return str(val).strip().lower().replace(" ", "").replace("-", "").replace("_", "").replace(".", "")

PREDICTION_COLS = []
for group_name in groups.keys():
    PREDICTION_COLS.extend([f"{group_name}_1st", f"{group_name}_2nd", f"{group_name}_3rd", f"{group_name}_4th"])

def connect_to_sheet(tab_name="sheet1"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("World_Cup_Pool_Data")
    if tab_name == "sheet1":
        return spreadsheet.sheet1
    return spreadsheet.worksheet(tab_name)

@st.cache_data(ttl=300) 
def get_live_standings():
    headers = {'X-Auth-Token': API_KEY}
    all_teams_ordered = []
    
    try:
        response = requests.get(f"{BASE_URL}?season=2026", headers=headers, timeout=10)
        data = response.json()
        
        if 'standings' in data:
            # Gather EVERY team in the order the API lists them, across all standings blocks
            for group_data in data['standings']:
                table = group_data.get('table', [])
                for row in table:
                    team_node = row.get('team', {})
                    raw_api_name = team_node.get('shortName') or team_node.get('name')
                    if raw_api_name:
                        lookup_key = standardize_string(raw_api_name)
                        clean_name = CLEAN_TEAM_MAP.get(lookup_key, str(raw_api_name).strip())
                        if clean_name not in all_teams_ordered:
                            all_teams_ordered.append(clean_name)
        
        if not all_teams_ordered:
            return MANUAL_LIVE_STANDINGS, True

        # Reconstruct the true 12 separate groups based on their ranking sequence in the master API list
        structured_live_map = {}
        for group_name, tracking_teams in groups.items():
            # Find which of this group's teams are in the master list, preserving their relative API order
            group_teams_in_api_order = [team for team in all_teams_ordered if team in tracking_teams]
            
            # If any teams are missing from active tracking, append them to the bottom safely
            for team in tracking_teams:
                if team not in group_teams_in_api_order:
                    group_teams_in_api_order.append(team)
                    
            structured_live_map[group_name] = group_teams_in_api_order
            
        return structured_live_map, False
    except Exception as e:
        return MANUAL_LIVE_STANDINGS, True

# --- APP UI SETUP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation", ["Leaderboard", "Make Predictions", "Rules & Chat Forum"])

with st.sidebar:
    st.header("Player Info")
    user_name = st.text_input("Full Name:")
    st.divider()
    st.markdown("### 📸 Official Instagram")
    st.write("Make sure you follow the official instagram **@2026fifawcp** for updates and general banter.")
    try:
        st.image("qr-code.png", caption="Scan to follow", use_container_width=True)
    except:
        st.caption("(QR Code image file missing in repository)")

# --- PAGE 1: LEADERBOARD ---
if page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")
    with st.spinner("Calculating live scores..."):
        live_standings_map, is_fallback = get_live_standings()
        
        try:
            sheet = connect_to_sheet()
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                
                rename_dict = {df.columns[0]: 'Timestamp', df.columns[1]: 'Name'}
                for idx, col_name in enumerate(PREDICTION_COLS):
                    if idx + 2 < len(df.columns):
                        rename_dict[df.columns[idx + 2]] = col_name
                if len(df.columns) > len(PREDICTION_COLS) + 2:
                    rename_dict[df.columns[-1]] = 'Status'
                
                df = df.rename(columns=rename_dict)
                if 'Status' not in df.columns:
                    df['Status'] = 'Pending'

                paid_count = df['Status'].astype(str).str.strip().str.lower().eq('paid').sum()
                total_pot = paid_count * 10

                metric_col1, metric_col2 = st.columns([3, 1])
                with metric_col1:
                    if is_fallback:
                        st.info("💡 Running on Local Standing Matrix fallback data.")
                    else:
                        st.success("✅ Connected and parsing Flat API Master Standings Feed.")
                with metric_col2:
                    st.metric(label="💰 Total Pool Pot", value=f"${total_pot} USD")
                
                st.divider()

                def calculate_live_user_score(row):
                    if not live_standings_map:
                        return 0
                    total_points = 0
                    
                    for group_name, teams in groups.items():
                        current_live_order = live_standings_map.get(group_name, [])
                        if not current_live_order:
                            continue
                            
                        p1 = standardize_string(row.get(f"{group_name}_1st", ""))
                        p2 = standardize_string(row.get(f"{group_name}_2nd", ""))
                        p3 = standardize_string(row.get(f"{group_name}_3rd", ""))
                        p4 = standardize_string(row.get(f"{group_name}_4th", ""))
                        
                        live_standardized = [standardize_string(team) for team in current_live_order]
                        
                        if len(live_standardized) >= 1 and p1 == live_standardized[0]:
                            total_points += 1
                        if len(live_standardized) >= 2 and p2 == live_standardized[1]:
                            total_points += 1
                        if len(live_standardized) >= 3 and p3 == live_standardized[2]:
                            total_points += 1
                        if len(live_standardized) >= 4 and p4 == live_standardized[3]:
                            total_points += 1
                                    
                    return total_points

                df['Points'] = df.apply(calculate_live_user_score, axis=1)
                leaderboard_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
                st.dataframe(leaderboard_df, use_container_width=True, hide_index=True, height=1200)
                
                with st.expander("🛠️ Diagnostics View (Verify Decoded Sub-Groups)"):
                    st.write("Parsed and isolated groups processed from the flat API list:")
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
        st.info("**USA:** Venmo @jhradecky  \n**Canada:** E-transfer julien.hradecky@gmail.com  \n**UK/EU:** Send a carrier pidgeon to Jack Johnson")
        st.write("**Prizes:** 1st: 70% | 2nd: 20% | 3rd: Refund")

    st.divider()
    st.header("💬 Chat Forum")
    with st.form("chat_form", clear_on_submit=True):
        comment = st.text_area("Share a question or talk some trash:")
        submitted = st.form_submit_button("Post Message")
        if submitted:
            if not user_name:
                st.error("Please enter your name in the sidebar before posting.")
            elif not comment:
                st.error("Message cannot be empty.")
            else:
                try:
                    chat_sheet = connect_to_sheet("Chat_Data")
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    chat_sheet.append_row([now, user_name, comment])
                    st.success("Message posted!")
                except:
                    st.error("Could not post message. Ensure the 'Chat_Data' tab exists.")

    try:
        chat_sheet = connect_to_sheet("Chat_Data")
        messages = chat_sheet.get_all_records()
        if messages:
            for msg in reversed(messages[-15:]):
                st.markdown(f"**{msg['User']}** ({msg['Timestamp']})")
                st.write(msg['Message'])
                st.divider()
        else:
            st.info("No messages yet. Be the first to start the conversation!")
    except:
        st.warning("Chat history is currently unavailable.")
