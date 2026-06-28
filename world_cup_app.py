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

R32_FALLBACK = {
    # All 16 R32 fixtures fully confirmed - hardcoded as source of truth for team names
    # API is still used for match status and scores only
    "M73": ("South Africa",  "Canada"),       # Sun 28 Jun 21:00
    "M74": ("Germany",       "Paraguay"),     # Mon 29 Jun 22:30
    "M75": ("Netherlands",   "Morocco"),      # Tue 30 Jun 03:00
    "M76": ("Brazil",        "Japan"),        # Mon 29 Jun 19:00
    "M77": ("France",        "Sweden"),       # Tue 30 Jun 23:00
    "M78": ("Ivory Coast",   "Norway"),       # Tue 30 Jun 19:00
    "M79": ("Mexico",        "Ecuador"),      # Wed 1 Jul 03:00
    "M80": ("England",       "DR Congo"),     # Wed 1 Jul 18:00
    "M81": ("USA",           "Bosnia"),       # Thu 2 Jul 02:00
    "M82": ("Belgium",       "Senegal"),      # Wed 1 Jul 22:00
    "M83": ("Australia",     "Egypt"),        # Fri 3 Jul 20:00
    "M84": ("Spain",         "Austria"),      # Thu 2 Jul 21:00
    "M85": ("Switzerland",   "Algeria"),      # Fri 3 Jul 05:00
    "M86": ("Argentina",     "Cape Verde"),   # Sat 4 Jul 00:00
    "M87": ("Portugal",      "Croatia"),      # Fri 3 Jul 01:00
    "M88": ("Colombia",      "Ghana"),        # Sat 4 Jul 03:30
}

R32_SLOTS = [
    {"match_no": 1,  "date": "Sun, 28 Jun, 21:00", "id_tag": "M73"},
    {"match_no": 2,  "date": "Mon, 29 Jun, 19:00", "id_tag": "M76"},
    {"match_no": 3,  "date": "Mon, 29 Jun, 22:30", "id_tag": "M74"},
    {"match_no": 4,  "date": "Tue, 30 Jun, 03:00", "id_tag": "M75"},
    {"match_no": 5,  "date": "Tue, 30 Jun, 19:00", "id_tag": "M78"},
    {"match_no": 6,  "date": "Tue, 30 Jun, 23:00", "id_tag": "M77"},
    {"match_no": 7,  "date": "Wed, 1 Jul, 03:00",  "id_tag": "M79"},
    {"match_no": 8,  "date": "Wed, 1 Jul, 18:00",  "id_tag": "M80"},
    {"match_no": 9,  "date": "Wed, 1 Jul, 22:00",  "id_tag": "M82"},
    {"match_no": 10, "date": "Thu, 2 Jul, 02:00",  "id_tag": "M81"},
    {"match_no": 11, "date": "Thu, 2 Jul, 21:00",  "id_tag": "M84"},
    {"match_no": 12, "date": "Fri, 3 Jul, 01:00",  "id_tag": "M87"},
    {"match_no": 13, "date": "Fri, 3 Jul, 05:00",  "id_tag": "M85"},
    {"match_no": 14, "date": "Fri, 3 Jul, 20:00",  "id_tag": "M83"},
    {"match_no": 15, "date": "Sat, 4 Jul, 00:00",  "id_tag": "M86"},
    {"match_no": 16, "date": "Sat, 4 Jul, 03:30",  "id_tag": "M88"},
]

BRACKET_MAPPING = {
    "ROUND_OF_16":    {"M89": ("M73","M76"), "M90": ("M74","M77"), "M91": ("M75","M82"), "M92": ("M78","M79"),
                       "M93": ("M80","M81"), "M94": ("M83","M84"), "M95": ("M85","M86"), "M96": ("M87","M88")},
    "QUARTER_FINALS": {"M97": ("M89","M90"), "M98": ("M91","M92"), "M99": ("M93","M94"), "M100": ("M95","M96")},
    "SEMI_FINALS":    {"M101": ("M97","M98"), "M102": ("M99","M100")},
    "FINAL":          {"M104": ("M101","M102")}
}

ROUND_SIZES = [
    ("ROUND_OF_32",    16, ["M73","M74","M75","M76","M77","M78","M79","M80","M81","M82","M83","M84","M85","M86","M87","M88"]),
    ("ROUND_OF_16",     8, ["M89","M90","M91","M92","M93","M94","M95","M96"]),
    ("QUARTER_FINALS",  4, ["M97","M98","M99","M100"]),
    ("SEMI_FINALS",     2, ["M101","M102"]),
    ("FINAL",           1, ["M104"]),
]

GROUP_STAGE_KEYWORDS = {"GROUP", "REGULAR", "PRELIMINARY", "QUALIFYING", "PLAY_OFF_ROUND", "THIRD_PLACE"}

# ── Helpers ────────────────────────────────────────────────────────────────────

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

# ── FIX 1: Cache the gspread client — auth happens ONCE, not every call ────────
@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

def get_spreadsheet():
    return get_gspread_client().open_by_key(SHEET_KEY)

def get_worksheet(tab_name, retries=3):
    for attempt in range(retries):
        try:
            spreadsheet = get_spreadsheet()
            if tab_name == "sheet1":
                return spreadsheet.sheet1
            try:
                return spreadsheet.worksheet(tab_name)
            except gspread.exceptions.WorksheetNotFound:
                if tab_name == "Knockout_Picks":
                    ws = spreadsheet.add_worksheet(title="Knockout_Picks", rows="1000", cols="7")
                    ws.append_row(["Timestamp","Name","Match_ID","Home_Score","Away_Score","Winner","Stage"])
                    return ws
                elif tab_name == "Chat_Data":
                    ws = spreadsheet.add_worksheet(title="Chat_Data", rows="1000", cols="3")
                    ws.append_row(["Timestamp","User","Message"])
                    return ws
                raise
        except gspread.exceptions.APIError as e:
            if "429" in str(e) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
            elif attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise e

# ── FIX 2: Cache ALL sheet reads — shared across all users ────────────────────

@st.cache_data(ttl=600)
def load_player_names():
    """Cached 10 min — players almost never change."""
    ws = get_worksheet("sheet1")
    names = ws.col_values(2)[1:]  # Only fetch column B, skip header
    return sorted([n.strip() for n in names if n.strip()])

@st.cache_data(ttl=30)
def load_knockout_picks():
    """Cached 30 sec — shared read for all users."""
    ws = get_worksheet("Knockout_Picks")
    records = ws.get_all_records()
    return records

@st.cache_data(ttl=60)
def load_group_picks():
    """Cached 60 sec — group stage is now closed."""
    ws = get_worksheet("sheet1")
    return ws.get_all_records()

@st.cache_data(ttl=30)
def load_chat():
    """Cached 30 sec."""
    ws = get_worksheet("Chat_Data")
    return ws.get_all_records()

def save_pick(new_row, retries=3):
    """
    FIX 3: Always APPEND, never read-then-update.
    Concurrency-safe: no two users can overwrite each other.
    Deduplication on display: keep latest row per (Name, Match_ID).
    """
    for attempt in range(retries):
        try:
            ws = get_worksheet("Knockout_Picks")
            ws.append_row(new_row)
            # Invalidate the cache so next load sees the new row
            load_knockout_picks.clear()
            return True
        except gspread.exceptions.APIError as e:
            if "429" in str(e) and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
            elif attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return False

# ── API fetchers (unchanged, already cached) ───────────────────────────────────

@st.cache_data(ttl=300)
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

@st.cache_data(ttl=300)
def fetch_all_knockout_matches():
    """
    R32 fixtures come from R32_FALLBACK (source of truth for teams).
    API is used ONLY to get match status and scores for R32, matched by team name.
    Later rounds (R16+) come from API by position once teams are known.
    This way wrong API team assignments can never corrupt our fixture display.
    """
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(f"{MATCHES_URL}?season=2026", headers=headers, timeout=12)
        if response.status_code != 200:
            all_matches = []
        else:
            all_matches = response.json().get('matches', [])
    except Exception:
        all_matches = []

    # Index all API knockout matches by team name for score/status lookup
    api_by_team = {}
    ko_by_stage = {}
    for m in all_matches:
        stage = str(m.get('stage', '')).upper()
        if is_group_stage(stage):
            continue
        ko_by_stage.setdefault(stage, []).append(m)
        for side in ['homeTeam', 'awayTeam']:
            team = m.get(side, {})
            # Try every possible field the API might use for team name
            raw = (team.get('name') or team.get('shortName') or
                   team.get('tla') or team.get('crestUrl') or '').strip()
            # Also try id-based lookup isn't helpful but log what we have
            if raw and raw != 'null':
                ct = clean_team(raw)
                api_by_team[ct] = m
                api_by_team[raw] = m  # also store raw in case clean_team misses it

    for stage in ko_by_stage:
        ko_by_stage[stage].sort(key=lambda x: x.get('utcDate', '9999'))

    tag_to_match = {}

    # ── R32: fallback is source of truth for team names ──────────────────────
    # API is used ONLY to get status/score, matched by team name.
    r32_tags = [tag for _, size, tags in ROUND_SIZES if size == 16 for tag in tags]
    assigned_ids = set()
    for tag in r32_tags:
        fb_home, fb_away = R32_FALLBACK.get(tag, ("TBD", "TBD"))
        # Find API match for score/status by looking up either confirmed team
        matched_m = None
        for name in [fb_home, fb_away]:
            if name != "TBD" and name in api_by_team:
                candidate = api_by_team[name]
                if candidate.get('id') not in assigned_ids:
                    matched_m = candidate
                    assigned_ids.add(candidate.get('id'))
                    break
        tag_to_match[tag] = {
            "home":      fb_home,
            "away":      fb_away,
            "status":    matched_m.get('status', 'SCHEDULED') if matched_m else 'SCHEDULED',
            "score":     matched_m.get('score', {}) if matched_m else {},
            "winner":    matched_m.get('score', {}).get('winner') if matched_m else None,
            "stage_raw": matched_m.get('stage', '') if matched_m else '',
            "api_id":    matched_m.get('id') if matched_m else None,
        }

    # ── Later rounds: purely from API by position ──────────────────────────────
    size_to_tags = {size: tags for _, size, tags in ROUND_SIZES if size < 16}
    used_stages = set()
    for _, size, tags in ROUND_SIZES:
        if size >= 16:
            continue
        # Find API stage with matching count
        api_matches = []
        for stage, matches in sorted(ko_by_stage.items(), key=lambda x: -len(x[1])):
            if stage not in used_stages and len(matches) == size:
                api_matches = matches
                used_stages.add(stage)
                break
        for i, tag in enumerate(tags):
            if i < len(api_matches):
                m = api_matches[i]
                h_raw = (m.get('homeTeam', {}).get('name') or m.get('homeTeam', {}).get('shortName') or '').strip()
                a_raw = (m.get('awayTeam', {}).get('name') or m.get('awayTeam', {}).get('shortName') or '').strip()
                tag_to_match[tag] = {
                    "home":   clean_team(h_raw) if h_raw else "TBD",
                    "away":   clean_team(a_raw) if a_raw else "TBD",
                    "status": m.get('status', 'SCHEDULED'),
                    "score":  m.get('score', {}),
                    "winner": m.get('score', {}).get('winner'),
                    "stage_raw": m.get('stage', ''),
                    "api_id": m.get('id'),
                }
            else:
                tag_to_match[tag] = {
                    "home": "TBD", "away": "TBD", "status": "SCHEDULED",
                    "score": {}, "winner": None, "stage_raw": "", "api_id": None
                }

    # Fill any gaps
    for _, _, tags in ROUND_SIZES:
        for tag in tags:
            if tag not in tag_to_match:
                tag_to_match[tag] = {
                    "home": "TBD", "away": "TBD", "status": "SCHEDULED",
                    "score": {}, "winner": None, "stage_raw": "", "api_id": None
                }

    tag_to_match["__debug__"] = {
        "total_api_matches": len(all_matches),
        "knockout_by_stage": {s: len(v) for s, v in ko_by_stage.items()},
        "api_teams_found": list(api_by_team.keys())[:20],
        "raw_sample": [
            {"stage": m.get('stage'), "homeTeam": m.get('homeTeam'), "awayTeam": m.get('awayTeam')}
            for m in list(ko_by_stage.get('LAST_32', ko_by_stage.get(list(ko_by_stage.keys())[0], [])) if ko_by_stage else [])[:3]
        ],
    }
    return tag_to_match


# ── App setup ──────────────────────────────────────────────────────────────────

st.set_page_config(page_title="2026 WC Portal", layout="wide")
page = st.sidebar.radio("Navigation Menu", [
    "Knockout Predictions", "Leaderboard", "Group Predictions (Closed)", "Rules & Chat Forum"
])

# Load player names from cache — one read shared by everyone
try:
    registered_players = load_player_names()
    if registered_players:
        st.session_state["player_list_cache"] = registered_players
except Exception:
    registered_players = []

if not registered_players and "player_list_cache" in st.session_state:
    registered_players = st.session_state["player_list_cache"]

with st.sidebar:
    st.header("Player Login")
    if registered_players:
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
elif page == "Leaderboard":
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
            raw_group_records = load_group_picks()
            group_df = pd.DataFrame(raw_group_records) if raw_group_records else pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Could not load group picks: {e}")
            group_df = pd.DataFrame()

        try:
            raw_ko_records = load_knockout_picks()
            ko_df = pd.DataFrame(raw_ko_records) if raw_ko_records else pd.DataFrame()
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

        # FIX 4: Deduplicate knockout picks — keep latest row per (Name, Match_ID)
        if not ko_df.empty and 'Timestamp' in ko_df.columns:
            ko_df = ko_df.sort_values('Timestamp').groupby(
                ['Name','Match_ID'], as_index=False).last()

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
                ft = match_info.get('score', {})
                # Use extraTime score if available (accounts for 120 min), else fullTime (90 min)
                final = ft.get('extraTime') or ft.get('fullTime', {})
                if final:
                    if final.get('home') is not None and str(pick.get('Home_Score', '')) == str(final['home']):
                        total += 1
                    if final.get('away') is not None and str(pick.get('Away_Score', '')) == str(final['away']):
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

        with st.expander("🛠️ Diagnostics"):
            debug = tag_to_match.get("__debug__", {})
            st.write(f"Total API matches: `{debug.get('total_api_matches','?')}`")
            st.write(f"Stage names: `{debug.get('knockout_by_stage',{})}`")
            st.write(f"API teams found: `{debug.get('api_teams_found',[])}`")
            st.write("**R32 tag mapping:**")
            r32 = {k: {"home": v["home"], "away": v["away"], "status": v["status"]} for k, v in tag_to_match.items() if k.startswith("M") and k not in ["M89","M90","M91","M92","M93","M94","M95","M96","M97","M98","M99","M100","M101","M102","M104"]}
            st.json(r32)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: KNOCKOUT PREDICTIONS
# ══════════════════════════════════════════════════════════════════════════════
if page == "Knockout Predictions":
    st.title("🏆 Interactive Knockout Bracket Engine")

    tag_to_match = fetch_all_knockout_matches()

    if not user_name:
        st.info("👈 Authenticate to open your bracket.")
    else:
        st.success(f"Log-In User: **{user_name}**")

        # FIX 5: Read knockout picks ONCE from cache, never inside draw_match_ui
        try:
            raw_ko = load_knockout_picks()
            all_ko_df = pd.DataFrame(raw_ko) if raw_ko else pd.DataFrame()
        except Exception as e:
            st.error(f"❌ Could not load picks: {e}")
            st.stop()

        # Deduplicate — keep latest per (Name, Match_ID)
        if not all_ko_df.empty and 'Timestamp' in all_ko_df.columns:
            all_ko_df = all_ko_df.sort_values('Timestamp').groupby(
                ['Name','Match_ID'], as_index=False).last()

        user_ko_df = all_ko_df[
            all_ko_df['Name'].astype(str).str.lower() == user_name.strip().lower()
        ] if not all_ko_df.empty else pd.DataFrame()

        if not user_ko_df.empty:
            for _, row in user_ko_df.iterrows():
                st.session_state.ko_winners[str(row['Match_ID'])] = str(row['Winner'])

        # FIX 6: draw_match_ui takes pre-loaded data — zero sheet reads inside
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
                        chosen_winner = st.selectbox("Advances via Penalty Kicks:", opts, index=idx,
                                                     key=f"pk_w_{tag}", disabled=is_locked)
                    else:
                        chosen_winner = home if h_score > a_score else away
                        st.markdown(f"<br><p><b>Advances:</b> {chosen_winner}</p>", unsafe_allow_html=True)

                st.session_state.ko_winners[tag] = chosen_winner if not exist_row.empty else None

                sub_c1, sub_c2 = st.columns([2,2])
                with sub_c1:
                    if st.button("Lock Score", key=f"btn_s_{tag}", disabled=is_locked):
                        new_row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                   user_name.strip(), tag,
                                   int(h_score), int(a_score), chosen_winner, stage]
                        if save_pick(new_row):
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
            home = info.get("home","TBD")
            away = info.get("away","TBD")
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
                    # Only show a team if the user has actually saved a pick for that feeder match
                    home = st.session_state.ko_winners.get(src_h) or "TBD"
                    away = st.session_state.ko_winners.get(src_a) or "TBD"
                is_locked = info.get("status") not in ["TIMED","SCHEDULED",None,""]
                draw_match_ui(m_id, home, away, is_locked, 0, None, stage)

        st.write("---")
        st.subheader("🏁 Tie-Breaker")
        tb_default = 0
        if not user_ko_df.empty and 'TIE_BREAKER' in user_ko_df['Match_ID'].values:
            tb_default = int(user_ko_df[user_ko_df['Match_ID'] == 'TIE_BREAKER']['Home_Score'].iloc[0])
        tb_val = st.number_input("Total goals in knockout stage:", min_value=0, value=tb_default)
        if st.button("Submit Tie-Breaker"):
            new_row = [datetime.now().strftime("%Y-%m-%d"), user_name, "TIE_BREAKER", tb_val, 0, "N/A", "TIE"]
            if save_pick(new_row):
                st.success("Tie-breaker submitted!")
                st.rerun()
            else:
                st.error("❌ Failed to save.")

        with st.expander("🛠️ API Debug"):
            debug = tag_to_match.get("__debug__", {})
            st.write(f"Total API matches: `{debug.get('total_api_matches','?')}`")
            st.write(f"Stages: `{debug.get('knockout_by_stage',{})}`")
            st.write(f"API teams found: `{debug.get('api_teams_found',[])}`")

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

    with st.expander("💰 Entry Fee & Prizes", expanded=True):
        st.write("**Entry Fee:** $10 USD / $15 CAD / £7.50 GBP")
        st.info("**USA:** Venmo @jhradecky  \n**Canada:** E-transfer julien.hradecky@gmail.com")
        st.write("**Prize Distribution:** 1st place: 70% | 2nd place: 20% | 3rd place: Full refund")
        st.warning("⚠️ All knockout picks must be submitted before each match kicks off.")

    with st.expander("📋 Scoring System", expanded=True):
        st.markdown("### Group Stage *(now closed)*")
        st.write("1 point per correct finishing position in each group (1st, 2nd, 3rd, 4th).")
        st.write("Maximum: 4 points per group × 12 groups = **48 points total**.")

        st.markdown("### Knockout Rounds")
        st.write("For each knockout match you predict:")
        st.markdown("""
| Correct prediction | Points |
|---|---|
| Exact home team score | 1 pt |
| Exact away team score | 1 pt |
| Correct winner / team that advances | 1 pt |
""")
        st.write("**Maximum 3 points per match** × 31 knockout matches = **93 points total.**")
        st.info("💡 If a match goes to extra time or penalties, the score you predict is the score after up to 120 minutes (including extra time). The winner pick is whoever actually advances (regardless of whether it goes to penalty kicks).")

    with st.expander("🏁 Tie-Breaker", expanded=True):
        st.markdown("### How the Tie-Breaker Works")
        st.write("At the bottom of the Knockout Predictions page, you submit a single number: your prediction for the **total number of goals scored across all 31 knockout matches** (excluding the third-place playoff).")
        st.write("The tie-breaker is only used if two or more players are level on points at the end of the tournament. The player whose tie-breaker guess is **closest to the actual total** wins the tiebreak.")
        st.write("If two players are still tied after the tie-breaker, the one who submitted their picks **earliest** wins.")
        st.info("💡 Tip: The 2022 World Cup knockout stage (16 matches) produced 64 goals. With 31 matches this time, somewhere in the 100–140 range is a reasonable starting point — but it's your call!")

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
                    ws = get_worksheet("Chat_Data")
                    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_name, comment])
                    load_chat.clear()
                    st.success("Message posted!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not post message: {e}")

    try:
        messages = load_chat()
        if messages:
            for msg in reversed(messages[-20:]):
                st.markdown(f"**{msg.get('User','')}** ({msg.get('Timestamp','')})")
                st.write(msg.get('Message',''))
                st.divider()
        else:
            st.info("No messages yet. Be the first!")
    except Exception as e:
        st.warning(f"Chat history unavailable: {e}")
