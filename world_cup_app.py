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

# --- BULLETPROOF API-TO-LOCAL TEAM MAPPER ---
# Maps the precise strings returned by the football-data.org API to your local group list values
TEAM_TRANSLATION = {
    "mexico national football team": "Mexico",
    "south africa national soccer team": "South Africa",
    "south korea national football team": "South Korea",
    "czech republic national football team": "Czechia",
    "czechia national football team": "Czechia",
    "canada men's national soccer team": "Canada",
    "switzerland": "Switzerland",
    "switzerland national football team": "Switzerland",
    "qatar national football team": "Qatar",
    "bosnia and herzegovina national football team": "Bosnia",
    "brazil national football team": "Brazil",
    "morocco national football team": "Morocco",
    "haiti national football team": "Haiti",
    "scotland national football team": "Scotland",
    "united states men's national soccer team": "USA",
    "usa national football team": "USA",
    "paraguay national football team": "Paraguay",
    "australia national football team": "Australia",
    "türkiye national football team": "Türkiye",
    "turkey national football team": "Türkiye",
    "germany national football team": "Germany",
    "curaçao national football team": "Curaçao",
    "ivory coast national football team": "Ivory Coast",
    "ecuador national football team": "Ecuador",
    "netherlands national football team": "Netherlands",
    "japan national football team": "Japan",
    "assign men's national soccer team": "Sweden",
    "sweden men's national football team": "Sweden",
    "tunisia national football team": "Tunisia",
    "belgium national football team": "Belgium",
    "egypt national football team": "Egypt",
    "iran national football team": "Iran",
    "new zealand national football team": "New Zealand",
    "assign national football team": "Spain",
    "spaniard national football team": "Spain",
    "spain national football team": "Spain",
    "cabo verde national football team": "Cape Verde",
    "cape verde national football team": "Cape Verde",
    "saudi arabia national football team": "Saudi Arabia",
    "uruguay national football team": "Uruguay",
    "france national football team": "France",
    "senegal national football team": "Senegal",
    "norway national football team": "Norway",
    "iraq national football team": "Iraq",
    "argentina national football team": "Argentina",
    "algeria national football team": "Algeria",
    "austria national football team": "Austria",
    "jordan national football team": "Jordan",
    "portugal national football team": "Portugal",
    "uzbekistan national football team": "Uzbekistan",
    "colombia national football team": "Colombia",
    "dr congo national football team": "DR Congo",
    "england national football team": "England",
    "croatia national football team": "Croatia",
    "ghana national football team": "Ghana",
    "panama national football team": "Panama"
}

# Generate flat list of dynamic column headers for safe data mapping
PREDICTION_COLS = []
for group_name in groups.keys():
    PREDICTION_COLS.extend([f"{group_name}_1st", f"{group_name}_2nd", f"{group_name}_3rd", f"{group_name}_4th"])

# --- GOOGLE SHEETS CONNECTION ---
def connect_to_sheet(tab_name="sheet1"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("World_Cup_Pool_Data")
    if tab_name == "sheet1":
        return spreadsheet.sheet1
    return spreadsheet.worksheet(tab_name)

# --- API DATA FETCHING (LIVE LIVE STANDINGS MAP) ---
@st.cache_data(ttl=300) 
def get_live_standings():
    """
    Fetches live standings and constructs a dictionary mapping:
    Group Letter ("A", "B", etc.) -> List of teams converted to your local short names
    """
    headers = {'X-Auth-Token': API_KEY}
    live_map = {}
    try:
        response = requests.get(f"{BASE_URL}?season=2026", headers=headers)
        data = response.json()
        
        if 'standings' in data:
            for group_data in data['standings']:
                group_raw = str(group_data.get('group', '')).upper().strip()
                
                table = group_data.get('table', [])
                translated_team_order = []
                for row in table:
                    raw_api_name = row.get('team', {}).get('name')
                    if raw_api_name:
                        norm_name = str(raw_api_name).strip().lower()
                        # Translate the long API team name into your specific localized short string
                        clean_name = TEAM_TRANSLATION.get(norm_name, str(raw_api_name).strip())
                        translated_team_order.append(clean_name)
                
                if not translated_team_order:
                    continue

                detected_letter = None
                
                # 1. Parse standard identifier format (e.g. "GROUP_A")
                if '_' in group_raw:
                    possible_letter = group_raw.split('_')[1]
                    if possible_letter in [g.split(" ")[1] for g in groups.keys()]:
                        detected_letter = possible_letter

                # 2. Fallback: Identify group context by matching any translated team to your local schema
                if not detected_letter:
                    for group_name, tracking_teams in groups.items():
                        if any(t in tracking_teams for t in translated_team_order):
                            detected_letter = group_name.split(" ")[1]
                            break
                
                if detected_letter:
                    live_map[detected_letter] = translated_team_order
                    
        return live_map
    except Exception as e:
        return {}

# --- APP UI SETUP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation", ["Leaderboard", "Make Predictions", "Rules"])

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
    with st.spinner("Calculating live scores from current match data..."):
        live_standings_map = get_live_standings()
        
        try:
            sheet = connect_to_sheet()
            records = sheet.get_all_records()
            if records:
                df = pd.DataFrame(records)
                
                # Align Google Sheet columns to structured keys
                rename_dict = {df.columns[0]: 'Timestamp', df.columns[1]: 'Name'}
                for idx, col_name in enumerate(PREDICTION_COLS):
                    if idx + 2 < len(df.columns):
                        rename_dict[df.columns[idx + 2]] = col_name
                if len(df.columns) > len(PREDICTION_COLS) + 2:
                    rename_dict[df.columns[-1]] = 'Status'
                
                df = df.rename(columns=rename_dict)

                if 'Status' not in df.columns:
                    df['Status'] = 'Pending'

                # --- POT CALCULATOR ---
                paid_count = df['Status'].astype(str).str.strip().str.lower().eq('paid').sum()
                total_pot = paid_count * 10

                # Top Metrics Section Layout
                metric_col1, metric_col2 = st.columns([3, 1])
                with metric_col1:
                    st.write("Real-time points are awarded based on active live standings!")
                with metric_col2:
                    st.metric(label="💰 Total Pool Pot", value=f"${total_pot} USD")
                
                st.divider()

                def calculate_live_user_score(row):
                    if not live_standings_map:
                        return 0
                        
                    total_points = 0
                    
                    for group_name, teams in groups.items():
                        group_letter = group_name.split(" ")[1].upper().strip() 
                        
                        current_live_order = live_standings_map.get(group_letter, [])
                        if not current_live_order:
                            continue
                            
                        p1 = str(row.get(f"{group_name}_1st", "")).strip()
                        p2 = str(row.get(f"{group_name}_2nd", "")).strip()
                        p3 = str(row.get(f"{group_name}_3rd", "")).strip()
                        
                        user_top_3 = [p1, p2, p3]
                        live_top_3 = current_live_order[:3] # Returns top 3 cleanly translated names
                        
                        # Clean execution check: Look for precise matches now that strings match perfectly
                        for pick in user_top_3:
                            if pick and pick != "--" and pick != "Pending":
                                if pick in live_top_3:
                                    total_points += 1
                                    
                    return total_points

                df['Points'] = df.apply(calculate_live_user_score, axis=1)
                
                leaderboard_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
                st.dataframe(leaderboard_df, use_container_width=True, hide_index=True, height=1200)
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

# --- PAGE 3: RULES ---
elif page == "Rules":
    st.title("📜 Pool Rules & Payment")
    
    with st.expander("View Full Rules & Payment Details", expanded=True):
        st.warning("⚠️ **Deadline:** All picks must be submitted before June 11, 2026.")
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
