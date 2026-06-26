import streamlit as st
import pandas as pd
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re

# --- CONFIGURATION & MAPPING ---
API_KEY = '63ba1313af494222bddfb7f14879b920' 
MATCHES_URL = "https://api.football-data.org/v4/competitions/WC/matches"

# 

CLEAN_TEAM_MAP = {
    "mexico": "Mexico", "southafrica": "South Africa", "southkorea": "South Korea",
    "canada": "Canada", "switzerland": "Switzerland", "qatar": "Qatar",
    "bosnia": "Bosnia", "brazil": "Brazil", "morocco": "Morocco", "haiti": "Haiti",
    "scotland": "Scotland", "usa": "USA", "paraguay": "Paraguay",
    "australia": "Australia", "türkiye": "Türkiye", "germany": "Germany",
    "curaçao": "Curaçao", "ivorycoast": "Ivory Coast", "ecuador": "Ecuador",
    "netherlands": "Netherlands", "japan": "Japan", "sweden": "Sweden",
    "tunisia": "Tunisia", "belgium": "Belgium", "egypt": "Egypt",
    "iran": "Iran", "newzealand": "New Zealand", "spain": "Spain",
    "capeverde": "Cape Verde", "saudiarabia": "Saudi Arabia", "uruguay": "Uruguay",
    "france": "France", "senegal": "Senegal", "norway": "Norway", "iraq": "Iraq",
    "argentina": "Argentina", "algeria": "Algeria", "austria": "Austria",
    "jordan": "Jordan", "portugal": "Portugal", "uzbekistan": "Uzbekistan",
    "colombia": "Colombia", "drcongo": "DR Congo", "england": "England",
    "croatia": "Croatia", "ghana": "Ghana", "panama": "Panama"
}

# --- CONNECTIVITY ---
def connect_to_sheet(tab_name="Knockout_Picks"):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open("World_Cup_Pool_Data")
    try:
        return spreadsheet.worksheet(tab_name)
    except:
        return spreadsheet.add_worksheet(title=tab_name, rows="1000", cols="7")

# --- UI LOGIC ---
st.set_page_config(page_title="2026 WC Portal", layout="wide")
st.title("🏆 Interactive Knockout Bracket")

# User Selection
registered_players = ["Player 1", "Player 2"] # Replace with your dynamic fetch
user_name = st.sidebar.selectbox("Identify Profile:", ["-- Select --"] + registered_players)

if user_name != "-- Select --":
    st.success(f"Editing for: {user_name}")
    
    # 1. Round of 32 Example Block (Updated UI)
    st.subheader("1️⃣ Round of 32")
    with st.container(border=True):
        col_h, col_vs, col_a = st.columns([2, 1, 2])
        
        # Team Names above inputs
        with col_h:
            st.markdown("##### South Africa")
            h_score = st.number_input("Score", min_value=0, key="h_sa")
        with col_vs:
            st.markdown("<br>VS", unsafe_allow_html=True)
        with col_a:
            st.markdown("##### Canada")
            a_score = st.number_input("Score", min_value=0, key="a_ca")
            
        if st.button("Save Match"):
            sheet = connect_to_sheet()
            sheet.append_row([datetime.now().strftime("%Y-%m-%d"), user_name, "R32_M1", h_score, a_score, ""])
            st.toast("Saved!")

    # 2. Tie Breaker Section
    st.write("---")
    st.subheader("🏁 Final Tie-Breaker")
    tb_val = st.number_input("Total goals scored in the entire knockout stage:", min_value=0, value=0)
    if st.button("Submit Tie-Breaker Prediction"):
        sheet = connect_to_sheet()
        sheet.append_row([datetime.now().strftime("%Y-%m-%d"), user_name, "TIE_BREAKER", 0, 0, tb_val])
        st.success("Tie-breaker recorded.")
else:
    st.info("Please select your name from the sidebar.")
