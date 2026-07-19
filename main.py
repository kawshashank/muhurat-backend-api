from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import ephem
import math
from datetime import datetime, timedelta
import pytz

# Initialize FastAPI App
app = FastAPI(title="Vijayshwar Jantri - Muhurat API")

# Allow your frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- TYPES & PAYLOADS ---
class MuhuratRequest(BaseModel):
    activity: str
    target_year: int
    selected_zone_name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None

# --- ASTRONOMICAL CONSTANTS & RULES ---

# Map frontend dropdown strings to Latitude, Longitude, and Timezone
ZONE_MAPPING = {
    "Delhi, India (IST)": (28.6139, 77.2090, "Asia/Kolkata"),
    "New York, USA (EST)": (40.7128, -74.0060, "America/New_York"),
    "Singapore (SGT)": (1.3521, 103.8198, "Asia/Singapore"),
    "London, UK (GMT)": (51.5074, -0.1278, "Europe/London"),
    "Los Angeles, USA (PST)": (34.0522, -118.2437, "America/Los_Angeles"),
    "Sydney, Australia (AEST)": (-33.8688, 151.2093, "Australia/Sydney"),
    "Dubai, UAE (GST)": (25.2048, 55.2708, "Asia/Dubai")
}

TITHIS = [
    "Pratipada", "Duya", "Truya", "Chorum", "Ponchum", "Sheyam", "Satam", 
    "Ashtami", "Navam", "Dahom", "Kahyom", "Duvadashi", "Truvahsh", "Chodah", "Purnima",
    "Pratipada", "Duya", "Truya", "Chorum", "Ponchum", "Sheyam", "Satam", 
    "Ashtami", "Navam", "Dahom", "Kahyom", "Duvadashi", "Truvahsh", "Chodah", "Amavasya"
]

FORBIDDEN_TITHIS = {4, 9, 14, 19, 24, 29, 30} 

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra", 
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", 
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", 
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha", 
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

ACTIVITY_RULES = {
    "VEHICLE_PURCHASE": ["Pushya", "Punarvasu", "Shravana", "Dhanishta", "Shatabhisha", "Swati"],
    "PROPERTY_SIGNING": ["Rohini", "Mrigashirsha", "Pushya", "Purva Phalguni", "Hasta", "Anuradha"],
    "GRIHA_PRAVESH": ["Rohini", "Mrigashirsha", "Pushya", "Chitra", "Anuradha", "Revati"],
    "GENERAL_AUSPICIOUS": ["Pushya", "Rohini", "Mrigashirsha", "Hasta", "Anuradha", "Revati"]
}

RAHU_KAAL_SEGMENTS = {0: 1, 1: 6, 2: 4, 3: 5, 4: 3, 5: 2, 6: 7}

# --- HELPER FUNCTIONS ---

def get_moon_and_sun_longitude(obs: ephem.Observer):
    sun = ephem.Sun(obs)
    moon = ephem.Moon(obs)
    sun_lon = math.degrees(ephem.Ecliptic(sun).lon)
    moon_lon = math.degrees(ephem.Ecliptic(moon).lon)
    return sun_lon, moon_lon

def get_astrology_for_day(current_date, lat, lon, local_tz):
    # Lock the start time to exactly 00:00:00 of the target timezone's calendar day
    local_midnight = local_tz.localize(datetime(current_date.year, current_date.month, current_date.day, 0, 0, 0))
    utc_midnight = local_midnight.astimezone(pytz.utc)

    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = utc_midnight
    
    try:
        # Get the next mathematical sunrise and sunset for this specific location
        sunrise = obs.next_rising(ephem.Sun())
        sunset = obs.next_setting(ephem.Sun())
        
        # Advance observer exactly to sunrise to check the Udaya Tithi
        obs.date = sunrise
        sun_lon, moon_lon = get_moon_and_sun_longitude(obs)
        
        relative_lon = (moon_lon - sun_lon) % 360
        tithi_index = int(relative_lon / 12) + 1
        nakshatra_index = int(moon_lon / (360 / 27))
        
        return {
            "tithi_index": tithi_index,
            "tithi_name": TITHIS[tithi_index - 1],
            "nakshatra_name": NAKSHATRAS[nakshatra_index],
            "sunrise": sunrise,
            "sunset": sunset
        }
    except Exception:
        return None

def calculate_rahu_kaal(sunrise_ephem, sunset_ephem, local_tz):
    # Find the local weekday of the sunrise to apply the correct Rahu Kaal formula
    sunrise_utc = pytz.utc.localize(sunrise_ephem.datetime())
    sunrise_local = sunrise_utc.astimezone(local_tz)
    weekday = sunrise_local.weekday()
    
    day_length = sunset_ephem - sunrise_ephem
    segment_length = day_length / 8
    segment_index = RAHU_KAAL_SEGMENTS[weekday]
    
    rahu_start = sunrise_ephem + (segment_length * segment_index)
    rahu_end = rahu_start + segment_length
    
    # THE FIX: Convert the float math back to an ephem.Date before calling datetime()
    return ephem.Date(rahu_start).datetime(), ephem.Date(rahu_end).datetime()

# --- MAIN API ENDPOINT ---

@app.post("/api/calculate-muhurat")
def calculate_muhurat(request: MuhuratRequest):
    # 1. Geographic & Timezone Grounding
    zone_info = ZONE_MAPPING.get(request.selected_zone_name, ZONE_MAPPING["Delhi, India (IST)"])
    lat, lon, tz_name = zone_info[0], zone_info[1], zone_info[2]
    local_tz = pytz.timezone(tz_name)
    
    try:
        if request.start_date and request.end_date:
            start = datetime.strptime(request.start_date, "%Y-%m-%d")
            end = datetime.strptime(request.end_date, "%Y-%m-%d")
        else:
            start = datetime.utcnow()
            end = start + timedelta(days=30)
            
        if (end - start).days > 90:
            end = start + timedelta(days=90)
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    allowed_nakshatras = ACTIVITY_RULES.get(request.activity, ACTIVITY_RULES["GENERAL_AUSPICIOUS"])
    
    results = []
    current = start
    
    # 2. Calculation Loop
    while current <= end:
        astro = get_astrology_for_day(current, lat, lon, local_tz)
        if not astro:
            current += timedelta(days=1)
            continue
            
        if astro["tithi_index"] in FORBIDDEN_TITHIS:
            current += timedelta(days=1)
            continue 
            
        if astro["nakshatra_name"] not in allowed_nakshatras:
            current += timedelta(days=1)
            continue
            
        rahu_start_utc, rahu_end_utc = calculate_rahu_kaal(astro["sunrise"], astro["sunset"], local_tz)
        
        # 3. Final Timezone Conversions for the UI
        sunrise_dt = pytz.utc.localize(astro["sunrise"].datetime()).astimezone(local_tz)
        sunset_dt = pytz.utc.localize(astro["sunset"].datetime()).astimezone(local_tz)
        rahu_s = pytz.utc.localize(rahu_start_utc).astimezone(local_tz)
        rahu_e = pytz.utc.localize(rahu_end_utc).astimezone(local_tz)
        
        paksha = "Shukla (Zoon Pachh)" if astro["tithi_index"] <= 15 else "Krishna (Gatta Pachh)"
        
        results.append({
            "date": sunrise_dt.strftime("%Y-%m-%d"),
            "start_time": sunrise_dt.strftime('%I:%M %p'),
            "end_time": sunset_dt.strftime('%I:%M %p'),
            "nakshatra": astro["nakshatra_name"],
            "tithi": f"{astro['tithi_name']} ({paksha})",
            "notes": f"Rahu Kaal to avoid: {rahu_s.strftime('%I:%M %p')} to {rahu_e.strftime('%I:%M %p')}"
        })
        
        current += timedelta(days=1)
        
    return {
        "status": "success",
        "echo_params": {
            "activity": request.activity,
            "timezone": request.selected_zone_name,
            "year": request.target_year
        },
        "results": results
    }