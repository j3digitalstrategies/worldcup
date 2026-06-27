import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import time

# --- CONFIGURATION ---
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

# Fallback fixture table — used when API returns NULL for a team.
# API takes priority when it has real data. Update TBDs as games are confirmed.
R32_FALLBACK = {
    "M73": ("South Africa", "Canada"),
    "M74": ("Brazil",       "Japan"),
    "M75": ("Germany",      "Paraguay"),
    "M76": ("Netherlands",  "Morocco"),
    "M77": ("Ivory Coast",  "Norway"),
    "M78": ("TBD",          "TBD"),
    "M79": ("Mexico",       "TBD"),
    "M80": ("TBD",          "TBD"),
    "M81": ("TBD",          "TBD"),
    "M82": ("USA",          "Bosnia"),
    "M83": ("TBD",          "TBD"),
    "M84": ("TBD",          "TBD"),
    "M85": ("Switzerland",  "TBD"),
    "M86": ("Australia",    "TBD"),
    "M87": ("Argentina",    "Cape Verde"),
    "M88": ("TBD",          "TBD"),
}

# Slot schedule: dates/times only — teams come from API (with fallback above)
R32_SLOTS = [
    {"match_no": 1,  "date": "Sun, 28 Jun, 21:00", "id_tag": "M73"},
    {"match_no": 2,  "date": "Mon, 29 Jun, 19:00", "id_tag": "M74"},
    {"match_no": 3,  "date": "Mon, 29 Jun, 22:30", "id_tag": "M75"},
    {"match_no": 4,  "date": "Tue, 30 Jun, 03:00", "id_tag": "M76"},
    {"match_no": 5,  "date": "Tue, 30 Jun, 19:00", "id_tag": "M77"},
    {"match_no": 6,  "date": "Tue, 30 Jun, 23:00", "id_tag": "M78"},
    {"match_no": 7,  "date": "Wed, 1 Jul, 03:00",  "id_tag": "M79"},
    {"match_no": 8,  "date": "Wed, 1 Jul, 18:00",  "id_tag": "M80"},
    {"match_no": 9,  "date": "Wed, 1 Jul, 22:00",  "id_tag": "M81"},
    {"match_no": 10, "date": "Thu, 2 Jul, 02:00",  "id_tag": "M82"},
    {"match_no": 11, "date": "Thu, 2 Jul, 21:00",  "id_tag": "M83"},
    {"match_no": 12, "date": "Fri, 3 Jul, 01:00",  "id_tag": "M84"},
    {"match_no": 13, "date": "Fri, 3 Jul, 05:00",  "id_tag": "M85"},
    {"match_no": 14, "date": "Fri, 3 Jul, 20:00",  "id_tag": "M86"},
    {"match_no": 15, "date": "Sat, 4 Jul, 00:00",  "id_tag": "M87"},
    {"match_no": 16, "date": "Sat, 4 Jul, 03:30",  "id_tag": "M88"},
]

BRACKET_MAPPING = {
    "ROUND_OF_16":    {"M89": ("M73","M76"), "M90": ("M74","M77"), "M91": ("M75","M82"), "M92": ("M78","M79"),
                       "M93": ("M80","M81"), "M94": ("M83","M84"), "M95": ("M85","M86"), "M96": ("M87","M88")},
    "QUARTER_FINALS": {"M97": ("M89","M90"), "M98": ("M91","M92"), "M99": ("M93","M94"), "M100": ("M95","M96")},
    "SEMI_FINALS":    {"M101": ("M97","M98"), "M102": ("M99","M100")},
    "FINAL":          {"M104": ("M101","M102")}
}

# How many matches per round — used to slice the chronologically sorted API list
ROUND_SIZES = [
    ("ROUND_OF_32",    16, ["M73","M74","M75","M76","M77","M78","M79","M80","M81","M82","M83","M84","M85","M86","M87","M88"]),
    ("ROUND_OF_16",     8, ["M89","M90","M91","M92","M93","M94","M95","M96"]),
    ("QUARTER_FINALS",  4, ["M97","M98","M99","M100"]),
    ("SEMI_FINALS",     2, ["M101","M102"]),
    ("FINAL",           1, ["M104"]),
]

# Group stage stage names to EXCLUDE from knockout list
GROUP_STAGE_KEYWORDS = {"GROUP", "REGULAR", "PRELIMINARY", "QUALIFYING", "PLAY_OFF_ROUND", "THIRD_PLACE"}

def standardize_string(val):
    if val is None: return ""
    cleaned = re.sub(r'[\s\xa0\u200b\u200c\u200d]+', '', str(val))
    return cleaned.lower().replace("-","").replace("_","").replace(".","")

def clean_team(raw):
    if not raw: return "TBD"
    s = standardize_string(raw)
    return CLEAN_TEAM_MAP.get(s, raw.strip()) or "TBD"

def is_group_stage(stage_str):
    s = str(stage_str).upper()
    return any(kw in s for kw in GROUP_STAGE_KEYWORDS)

def connect_to_sheet(tab_name="sheet1", retries=3):
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    for attempt in range(retries):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
            client = gspread.authorize(creds)
            spreadsheet = client.open_by_key(SHEET_KEY)
            if tab_name == "Knockout_Picks":
                try:
                    return spreadsheet.worksheet("Knockout_Picks")
                except gspread.exceptions.WorksheetNotFound:
                    ws = spreadsheet.add_worksheet(title="Knockout_Picks", rows="1000", cols="7")
                    ws.append_row(["Timestamp","Name","Match_ID","Home_Score","Away_Score","Winner","Stage"])
                    return ws
            if tab_name == "Chat_Data":
                try:
                    return spreadsheet.worksheet("Chat_Data")
                except gspread.exceptions.WorksheetNotFound:
                    ws = spreadsheet.add_worksheet(title="Chat_Data", rows="1000", cols="3")
                    ws.append_row(["Timestamp","User","Message"])
                    return ws
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
                if 'Name' in df.columns:
                    return sorted(list(df['Name'].astype(str).str.strip().unique()))
            return []
        except gspread.exceptions.APIError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                st.error("⚠️ Could not load player list. Please refresh.")
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
def fetch_group_standings():
    headers = {'X-Auth-Token': API_KEY}
    response = requests.get(f"{BASE_URL}?season=2026", headers=headers, timeout=12)
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")
    data = response.json()
    if 'standings' not in data or not data['standings']:
        raise Exception("Empty standings payload")

    updated_map = {}
    for block in data['standings']:
        clean_group_key = None
        raw_group_name = block.get('group')
        if raw_group_name:
            m = re.search(r'\b([A-L])\b|GROUP[\s_-]*([A-L])', str(raw_group_name).upper())
            if m:
                clean_group_key = f"Group {m.group(1) or m.group(2)}"
        if not clean_group_key or clean_group_key not in INITIAL_SEED_STANDINGS:
            for row in block.get('table', []):
                raw_name = row.get('team',{}).get('shortName') or row.get('team',{}).get('name')
                if raw_name:
                    cn = clean_team(raw_name)
                    for g_key, g_teams in groups.items():
                        if cn in g_teams:
                            clean_group_key = g_key
                            break
                if clean_group_key:
                    break
        if clean_group_key in INITIAL_SEED_STANDINGS:
            ordered_teams = []
            for row in block.get('table', []):
                raw_name = row.get('team',{}).get('shortName') or row.get('team',{}).get('name')
                if raw_name:
                    ordered_teams.append(clean_team(raw_name))
            for team in INITIAL_SEED_STANDINGS[clean_group_key]:
                if team not in ordered_teams:
                    ordered_teams.append(team)
            if len(ordered_teams) >= 4:
                updated_map[clean_group_key] = ordered_teams[:4]
    return updated_map

@st.cache_data(ttl=1800)
def fetch_all_knockout_matches():
    """
    Fetch all matches, exclude group stage by keyword, sort chronologically,
    then assign to M-tags in order. Works regardless of what stage names the API uses.
    Returns dict: { 'M73': { home, away, status, score, winner, stage_raw }, ... }
    """
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{MATCHES_URL}?season=2026", headers=headers, timeout=12)
        if response.status_code != 200:
            st.warning(f"⚠️ Matches API returned HTTP {response.status_code}")
            return {}
        all_matches = response.json().get('matches', [])
    except Exception as e:
        st.warning(f"⚠️ Could not fetch match data: {e}")
        return {}

    # Exclude group stage matches — everything else is knockout
    ko_matches = [m for m in all_matches if not is_group_stage(m.get('stage',''))]
    ko_matches.sort(key=lambda x: x.get('utcDate','9999-99-99'))

    # Store raw stage names so we can debug
    raw_stages = list({m.get('stage','?') for m in ko_matches})

    # Now bucket them by round size chronologically
    # football-data.org orders: R32 first, then R16, QF, SF, Final
    # We just slice in order — first 16 = R32, next 8 = R16, etc.
    tag_to_match = {}
    cursor = 0
    for round_name, size, tags in ROUND_SIZES:
        round_matches = ko_matches[cursor:cursor + size]
        cursor += size
        for i, tag in enumerate(tags):
            if i < len(round_matches):
                m = round_matches[i]
                h_raw = m.get('homeTeam',{}).get('name') or m.get('homeTeam',{}).get('shortName') or ''
                a_raw = m.get('awayTeam',{}).get('name') or m.get('awayTeam',{}).get('shortName') or ''
                h = clean_team(h_raw) if h_raw.strip() else "TBD"
                a = clean_team(a_raw) if a_raw.strip() else "TBD"
                # Apply fallback for R32 if API has NULLs
                if h == "TBD" or a == "TBD":
                    fb = R32_FALLBACK.get(tag, ("TBD","TBD"))
                    if h == "TBD": h = fb[0]
                    if a == "TBD": a = fb[1]
                tag_to_match[tag] = {
                    "home":      h,
                    "away":      a,
                    "status":    m.get('status','SCHEDULED'),
                    "score":     m.get('score',{}),
                    "winner":    m.get('score',{}).get('winner'),
                    "stage_raw": m.get('stage',''),
                    "api_id":    m.get('id'),
                }
            else:
                # No API match at all — use fallback
                fb = R32_FALLBACK.get(tag, ("TBD","TBD"))
                tag_to_match[tag] = {
                    "home": fb[0], "away": fb[1], "status": "SCHEDULED",
                    "score":{},"winner":None,"stage_raw":"","api_id":None
                }

    # Attach debug info
    tag_to_match["__debug__"] = {
        "total_ko_matches": len(ko_matches),
        "raw_stages": raw_stages,
        "sample": [
            {"utcDate": m.get('utcDate'), "stage": m.get('stage'),
             "home": m.get('homeTeam',{}).get('name','?'),
             "away": m.get('awayTeam',{}).get('name','?')}
            for m in ko_matches[:6]
        ]
    }
    return tag_to_match

# ── App setup ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation Menu", [
    "Leaderboard", "Knockout Predictions", "Group Predictions (Closed)", "Rules & Chat Forum"
])
registered_players = get_registered_players()

# Keep last known good player list in session state
# so a transient API failure doesn't wipe the login mid-session
if registered_players:
    st.session_state["player_list_cache"] = registered_players
elif "player_list_cache" in st.session_state:
    registered_players = st.session_state["player_list_cache"]

with st.sidebar:
    st.header("Player Login")
    if registered_players:
        # Preserve selected name across reruns
        prev = st.session_state.get("selected_player", "-- Select Profile --")
        opts = ["-- Select Profile --"] + registered_players
        default_idx = opts.index(prev) if prev in opts else 0
        selected = st.selectbox("Identify Profile Name:", opts, index=default_idx)
        st.session_state["selected_player"] = selected
        user_name = selected if selected != "-- Select Profile --" else ""
    else:
        st.warning("⚠️ Could not load player list. Try Sync below.")
        user_name = ""
    st.divider()
    st.markdown("### 📸 Official Instagram")
    st.write("Follow **@2026fifawcp** for updates.")
    try:
        st.image("qr-code.png", caption="Scan to follow", use_container_width=True)
    except:
        st.caption("(QR Code image file missing)")
    st.divider()
    if st.button("🔄 Clear System Cache / Sync Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if "ko_winners" not in st.session_state:
    st.session_state.ko_winners = {}

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: LEADERBOARD
# ══════════════════════════════════════════════════════════════════════════════
if page == "Leaderboard":
    st.title("📊 Live Automated Leaderboard")

    if "group_standings_cache" not in st.session_state:
        st.session_state["group_standings_cache"] = INITIAL_SEED_STANDINGS

    with st.spinner("Loading live data..."):
        try:
            api_group_data = fetch_group_standings()
            merged = dict(st.session_state["group_standings_cache"])
            merged.update(api_group_data)
            st.session_state["group_standings_cache"] = merged
            group_sync_msg = f"✅ Group standings synced at {datetime.now().strftime('%H:%M')}"
            group_sync_ok = True
        except Exception as e:
            group_sync_msg = f"⚠️ Using cached group standings ({e})"
            group_sync_ok = False

        live_standings_map = st.session_state["group_standings_cache"]
        tag_to_match = fetch_all_knockout_matches()

        try:
            sheet = connect_to_sheet("sheet1")
            records = sheet.get_all_records()
            group_df = pd.DataFrame(records) if records else pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Could not load group picks: {e}")
            group_df = pd.DataFrame()

        try:
            ko_sheet = connect_to_sheet("Knockout_Picks")
            ko_records = ko_sheet.get_all_records()
            ko_df = pd.DataFrame(ko_records) if ko_records else pd.DataFrame()
        except Exception as e:
            st.warning(f"⚠️ Could not load knockout picks: {e}")
            ko_df = pd.DataFrame()

    if group_sync_ok:
        st.success(group_sync_msg)
    else:
        st.warning(group_sync_msg)

    if group_df.empty:
        st.info("No entries yet.")
    else:
        rename_dict = {}
        if len(group_df.columns) >= 2:
            rename_dict[group_df.columns[0]] = 'Timestamp'
            rename_dict[group_df.columns[1]] = 'Name'
        for col in group_df.columns:
            clean_col = re.sub(r'\s+','',str(col)).upper()
            m = re.match(r'^([A-L][1-4])$', clean_col)
            if m:
                rename_dict[col] = m.group(1)
            elif clean_col == 'STATUS':
                rename_dict[col] = 'Status'
        group_df = group_df.rename(columns=rename_dict)
        if 'Status' not in group_df.columns:
            group_df['Status'] = 'Pending'

        paid_count = group_df['Status'].astype(str).str.strip().str.lower().eq('paid').sum()
        st.metric("💰 Total Pool Pot", f"${paid_count * 10} USD")
        st.divider()

        def calc_group_points(row):
            total = 0
            for letter in "ABCDEFGHIJKL":
                live_order = live_standings_map.get(f"Group {letter}", [])
                if not live_order or len(live_order) < 4:
                    continue
                for pos in range(1, 5):
                    pick_raw = str(row.get(f"{letter}{pos}", ""))
                    pick = CLEAN_TEAM_MAP.get(standardize_string(pick_raw), pick_raw.strip())
                    if pick and pick == live_order[pos - 1]:
                        total += 1
            return total

        def calc_knockout_points(player_name):
            if ko_df.empty:
                return 0
            user_picks = ko_df[ko_df['Name'].astype(str).str.lower() == str(player_name).lower()]
            total = 0
            for _, pick in user_picks.iterrows():
                m_tag = str(pick.get('Match_ID',''))
                match_info = tag_to_match.get(m_tag)
                if not match_info or match_info.get('status') not in ['FINISHED','AWARDED']:
                    continue
                ft = match_info.get('score',{}).get('fullTime',{})
                if ft:
                    if ft.get('home') is not None and str(pick.get('Home_Score','')) == str(ft['home']):
                        total += 1
                    if ft.get('away') is not None and str(pick.get('Away_Score','')) == str(ft['away']):
                        total += 1
                api_winner = match_info.get('winner')
                if api_winner:
                    actual_adv = match_info['home'] if api_winner == 'HOME_TEAM' else match_info['away']
                    if standardize_string(str(pick.get('Winner',''))) == standardize_string(actual_adv):
                        total += 1
            return total

        group_df['Group_Points']    = group_df.apply(calc_group_points, axis=1)
        group_df['Knockout_Points'] = group_df['Name'].apply(calc_knockout_points)
        group_df['Points']          = group_df['Group_Points'] + group_df['Knockout_Points']

        leaderboard_df = group_df[['Name','Points','Group_Points','Knockout_Points','Status']] \
            .sort_values(by='Points', ascending=False).reset_index(drop=True)

        st.subheader("Current Standings")
        hcols = st.columns([2,1,1,1,1,2])
        for label, col in zip(["**Name**","**Total**","**Group**","**Knockout**","**Status**","**Download**"], hcols):
            col.markdown(label)
        st.divider()

        for _, row in leaderboard_df.iterrows():
            cols = st.columns([2,1,1,1,1,2])
            cols[0].write(row['Name'])
            cols[1].write(int(row['Points']))
            cols[2].write(int(row['Group_Points']))
            cols[3].write(int(row['Knockout_Points']))
            cols[4].write(row['Status'])
            csv = group_df[group_df['Name'] == row['Name']].to_csv(index=False).encode('utf-8')
            cols[5].download_button("📥 CSV", data=csv,
                file_name=f"{row['Name']}_picks.csv", key=f"dl_{row['Name']}")

        with st.expander("🛠️ Diagnostics — click to debug API data"):
            st.write("**Knockout matches from API:**")
            debug = tag_to_match.get("__debug__", {})
            st.write(f"Total knockout matches found: `{debug.get('total_ko_matches', '?')}`")
            st.write(f"Stage names seen: `{debug.get('raw_stages', [])}`")
            st.write("First 6 matches:")
            st.json(debug.get("sample", []))
            st.write("**Tag → Match mapping (R32):**")
            r32_preview = {k: {"home": v["home"], "away": v["away"], "status": v["status"]}
                           for k, v in tag_to_match.items() if k.startswith("M") and k != "M10"}
            st.json(r32_preview)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: KNOCKOUT PREDICTIONS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Knockout Predictions":
    st.title("🏆 Interactive Knockout Bracket Engine")

    tag_to_match = fetch_all_knockout_matches()

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
            for _, row in user_ko_df.iterrows():
                st.session_state.ko_winners[str(row['Match_ID'])] = str(row['Winner'])

        def draw_match_ui(tag, home, away, is_locked, match_no, date, stage):
            exist_row = user_ko_df[user_ko_df['Match_ID'].astype(str) == tag] \
                if not user_ko_df.empty else pd.DataFrame()
            default_h = int(exist_row['Home_Score'].values[0]) if not exist_row.empty else 0
            default_a = int(exist_row['Away_Score'].values[0]) if not exist_row.empty else 0
            default_w = str(exist_row['Winner'].values[0]) if not exist_row.empty else home

            with st.container():
                st.write("---")
                if date: st.caption(f"📅 Match {match_no} • {date}")
                c1, c2, c3, c4 = st.columns([3,1,3,3])
                with c1:
                    st.markdown(f"**{home}**")
                    h_score = st.number_input("Goals", min_value=0, value=default_h,
                                              key=f"h_s_{tag}", disabled=is_locked)
                with c2:
                    st.markdown("<br><p style='text-align:center;'>VS</p>", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"**{away}**")
                    a_score = st.number_input("Goals", min_value=0, value=default_a,
                                              key=f"a_s_{tag}", disabled=is_locked)
                with c4:
                    if h_score == a_score:
                        opts = [home, away]
                        idx = opts.index(default_w) if default_w in opts else 0
                        chosen_winner = st.selectbox("Advances via PKs:", opts, index=idx,
                                                     key=f"pk_w_{tag}", disabled=is_locked)
                    else:
                        chosen_winner = home if h_score > a_score else away
                        st.markdown(f"<br><p><b>Advances:</b> {chosen_winner}</p>", unsafe_allow_html=True)

                st.session_state.ko_winners[tag] = chosen_winner

                sub_c1, sub_c2 = st.columns([2,2])
                with sub_c1:
                    if st.button("Lock Score", key=f"btn_s_{tag}", disabled=is_locked):
                        existing = ko_sheet.get_all_records()
                        row_i = next((i + 2 for i, r in enumerate(existing)
                                      if str(r.get('Name','')).lower() == user_name.lower()
                                      and str(r.get('Match_ID','')) == tag), -1)
                        new_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   user_name.strip(), tag, int(h_score), int(a_score), chosen_winner, stage]
                        if save_pick_with_retry(ko_sheet, row_i, new_row):
                            st.toast("✅ Saved!")
                            st.rerun()
                        else:
                            st.error("❌ Failed to save. Please try again.")
                with sub_c2:
                    if not exist_row.empty:
                        st.markdown("🟢 **Submitted**")

        st.subheader("1️⃣ Round of 32")
        for slot in R32_SLOTS:
            tag  = slot["id_tag"]
            info = tag_to_match.get(tag, {})
            home = info.get("home", "TBD")
            away = info.get("away", "TBD")
            is_locked = info.get("status") not in ["TIMED","SCHEDULED",None,""]
            draw_match_ui(tag, home, away, is_locked, slot["match_no"], slot["date"], "ROUND_OF_32")

        for stage, label in [("ROUND_OF_16","2️⃣ R16"), ("QUARTER_FINALS","3️⃣ QF"),
                              ("SEMI_FINALS","4️⃣ SF"), ("FINAL","5️⃣ Final")]:
            st.subheader(label)
            for m_id, (src_h, src_a) in BRACKET_MAPPING[stage].items():
                info = tag_to_match.get(m_id, {})
                if info.get("home","TBD") != "TBD":
                    home = info["home"]
                    away = info["away"]
                else:
                    home = st.session_state.ko_winners.get(src_h, f"Winner {src_h}")
                    away = st.session_state.ko_winners.get(src_a, f"Winner {src_a}")
                is_locked = info.get("status") not in ["TIMED","SCHEDULED",None,""]
                draw_match_ui(m_id, home, away, is_locked, 0, None, stage)

        st.write("---")
        st.subheader("🏁 Tie-Breaker")
        tb_default = 0
        if not user_ko_df.empty and 'TIE_BREAKER' in user_ko_df['Match_ID'].values:
            tb_default = int(user_ko_df[user_ko_df['Match_ID'] == 'TIE_BREAKER']['Home_Score'].iloc[0])
        tb_val = st.number_input("Total goals in knockout stage:", min_value=0, value=tb_default)
        if st.button("Submit Tie-Breaker"):
            if save_pick_with_retry(ko_sheet, -1,
                [datetime.now().strftime("%Y-%m-%d"), user_name, "TIE_BREAKER", tb_val, 0, "N/A", "TIE"]):
                st.success("Tie-breaker submitted!")
                st.rerun()
            else:
                st.error("❌ Failed to save.")

        with st.expander("🛠️ API Debug — what is the API sending?"):
            debug = tag_to_match.get("__debug__", {})
            st.write(f"Total knockout matches from API: `{debug.get('total_ko_matches','?')}`")
            st.write(f"Stage names seen: `{debug.get('raw_stages', [])}`")
            st.write("First 6 knockout matches:")
            st.json(debug.get("sample", []))

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: GROUP PREDICTIONS (CLOSED)
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Group Predictions (Closed)":
    st.title("🔒 Group Stage Predictions")
    st.warning("⚠️ The group stage prediction window is now closed.")
    st.info("Group stage picks are locked in. Points are being calculated automatically on the Leaderboard.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: RULES & CHAT FORUM
# ══════════════════════════════════════════════════════════════════════════════
elif page == "Rules & Chat Forum":
    st.title("📜 Pool Rules & Payment")
    with st.expander("View Full Rules & Payment Details", expanded=True):
        st.warning("⚠️ **Deadline:** All picks must be submitted before kick-off.")
        st.write("**Group Stage Scoring:** 1 point per correct finishing position (max 4 pts/group, 48 pts total).")
        st.write("**Knockout Scoring:** 1 pt correct home score + 1 pt correct away score + 1 pt correct winner (max 3 pts/match).")
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
                st.error("Please select your name in the sidebar.")
            elif not comment.strip():
                st.error("Message cannot be empty.")
            else:
                try:
                    chat_sheet = connect_to_sheet("Chat_Data")
                    chat_sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_name, comment])
                    st.success("Message posted!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not post message: {e}")

    try:
        chat_sheet = connect_to_sheet("Chat_Data")
        messages = chat_sheet.get_all_records()
        if messages:
            for msg in reversed(messages[-20:]):
                st.markdown(f"**{msg.get('User','')}** ({msg.get('Timestamp','')})")
                st.write(msg.get('Message',''))
                st.divider()
        else:
            st.info("No messages yet. Be the first!")
    except Exception as e:
        st.warning(f"Chat history unavailable: {e}")
