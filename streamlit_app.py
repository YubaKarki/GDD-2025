import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import json

# Load data
@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/EisingerSyngenta/FloweringData/main/2022%20Locations.csv"
    return pd.read_csv(url)

mydata = load_data()

# Set page config
st.set_page_config(page_title="GDU Calculator", layout="wide")

# Sidebar for inputs
st.sidebar.title("GDU Calculator")

# RSTCD Dropdown
rstcd_options = mydata['RSTCD'].unique()
rstcd = st.sidebar.selectbox("Select RSTCD", options=rstcd_options)

# LOCCD Dropdown
loccd_options = mydata[mydata['RSTCD'] == rstcd]['LOCCD'].unique() if rstcd else []
loccd = st.sidebar.selectbox("Select LOCCD", options=loccd_options)

# PLACD Dropdown
placd_options = mydata[(mydata['RSTCD'] == rstcd) & (mydata['LOCCD'] == loccd)]['PLACD'].unique() if loccd else []
placd = st.sidebar.selectbox("Select PLACD", options=placd_options)

# Date Range
if all([rstcd, loccd, placd]):
    available = mydata[(mydata['RSTCD'] == rstcd) & 
                       (mydata['LOCCD'] == loccd) & 
                       (mydata['PLACD'] == placd)]
    if not available.empty:
        planting_date = pd.to_datetime(available['planting_date'].iloc[0]).date()
        end_date = datetime.now().date()
        start_date = st.sidebar.date_input("Start Date", value=planting_date, min_value=datetime(2020,1,1).date(), max_value=end_date)
        end_date = st.sidebar.date_input("End Date", value=end_date, min_value=start_date, max_value=end_date)
    else:
        st.sidebar.error("No planting date found for the selected combination.")
else:
    st.sidebar.warning("Please select RSTCD, LOCCD, and PLACD to set date range.")

# Main content
st.title("GDU Data")

if all([rstcd, loccd, placd, start_date, end_date]):
    coords = mydata[(mydata['RSTCD'] == rstcd) & 
                    (mydata['LOCCD'] == loccd) & 
                    (mydata['PLACD'] == placd)][['Latitude', 'Longitude']]
    
    if coords.empty:
        st.error(f'No coordinates found for RSTCD: {rstcd}, LOCCD: {loccd}, PLACD: {placd}')
    else:
        lat, long = coords.iloc[0]
        
        payload = {
            "units": {
                "temperature": "F",
                "velocity": "mph",
                "length": "imperial",
                "energy": "watts"
            },
            "geometry": {
                "type": "MultiPoint",
                "coordinates": [[long, lat]],
                "locationNames": [""]
            },
            "format": "json",
            "timeIntervals": [f"{start_date}T00:00:00Z/{end_date}T23:59:59Z"],
            "timeIntervalsAlignment": "none",
            "queries": [{
                "domain": "ERA5",
                "gapFillDomain": "NEMSGLOBAL",
                "timeResolution": "daily",
                "codes": [{
                    "code": 731,
                    "level": "2 m elevation corrected",
                    "aggregation": "sum",
                    "gddBase": 50,
                    "gddLimit": 86
                }]
            }]
        }
        
        url = "http://my.meteoblue.com/dataset/query?apikey=syn82hw2eqe"
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            dates = [interval[:8] for interval in data[0]['timeIntervals'][0]]
            daily_gdu = data[0]['codes'][0]['dataPerTimeInterval'][0]['data'][0]
            
            dates = [datetime.strptime(date, '%Y%m%d').date() for date in dates]
            
            filtered_data = [(date, gdu) for date, gdu in zip(dates, daily_gdu) if start_date <= date <= end_date]
            
            if not filtered_data:
                st.warning('No data available for the selected date range')
            else:
                dates, daily_gdu = zip(*filtered_data)
                
                cumulative_gdu = [sum(daily_gdu[:i+1]) for i in range(len(daily_gdu))]
                
                df = pd.DataFrame({
                    'Date': dates,
                    'Daily GDU': [round(gdu, 2) for gdu in daily_gdu],
                    'Cumulative GDU': [round(gdu, 2) for gdu in cumulative_gdu]
                })
                
                st.dataframe(df)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download GDU Data as CSV",
                    data=csv,
                    file_name=f"{rstcd}_{loccd}_{placd}_GDU.csv",
                    mime="text/csv",
                )
                
        except requests.exceptions.RequestException as e:
            st.error(f'API request failed: {str(e)}')
else:
    st.info("Please select all required fields in the sidebar to view GDU data.")