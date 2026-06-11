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
    Group Letter -> List of teams in current standing order (index 0 is 1st, index 3 is 4th)
    Example: {"A": ["Mexico", "South Korea", "Czechia", "South Africa"], ...}
    """
    headers = {'X-Auth-Token': API_KEY}
    live_map = {}
    try:
        response = requests.get(f"{BASE_URL}?season=2026", headers=headers)
        data = response.json()
        
        if 'standings' in data:
            for group_data in data['standings']:
                group_raw = group_data.get('group', '')
                if '_' in group_raw:
                    group_letter = group_raw.split('_')[1] # Extracts "A", "B", "C"...
                else:
                    continue
                
                table = group_data.get('table', [])
                team_order = []
                for row in table:
                    team_name = row.get('team', {}).get('name')
                    if team_name:
                        team_order.append(str(team_name).strip())
                
                if team_order:
                    live_map[group_letter] = team_order
        return live_map
    except Exception as e:
        return {}

# --- APP UI SETUP ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
# REORDERED: Leaderboard is now the first and default index option
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
                # Check for row values exactly matching "Paid" (case-insensitive & stripped)
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
                        group_letter = group_name.split(" ")[1] 
                        
                        current_live_order = live_standings_map.get(group_letter, [])
                        if not current_live_order:
                            continue
                            
                        p1 = str(row.get(f"{group_name}_1st", "")).strip()
                        p2 = str(row.get(f"{group_name}_2nd", "")).strip()
                        p3 = str(row.get(f"{group_name}_3rd", "")).strip()
                        
                        user_top_3 = [p1, p2, p3]
                        live_top_3 = current_live_order[:3]
                        
                        for pick in user_top_3:
                            if pick and pick != "--" and pick != "Pending":
                                if pick in live_top_3:
                                    total_points += 1
                                    
                    return total_points

                df['Points'] = df.apply(calculate_live_user_score, axis=1)
                
                leaderboard_df = df[['Name', 'Points', 'Status']].sort_values(by='Points', ascending=False)
                
                # Height variable set to 1200px to expand the layout frame dramatically 
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
