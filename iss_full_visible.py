# This script calculates a schedule of International Space Station 
# passes that are visible to the naked eye from a user-provided 
# street address by filtering for moments when the station is 
# sunlit against a dark, local sky.

import sys
import requests
import pytz
from datetime import datetime, timedelta
from skyfield.api import load, utc, wgs84

# --- HELPER FUNCTIONS ---

def get_coords(address, zipcode):
    url = "https://geocoding.geo.census.gov/geocoder/locations/address"
    params = {"street": address, "zip": zipcode, "benchmark": "Public_AR_Current", "format": "json"}
    try:
        response = requests.get(url, params=params)
        data = response.json()
        matches = data.get("result", {}).get("addressMatches", [])
        return (matches[0]["coordinates"]["y"], matches[0]["coordinates"]["x"]) if matches else None
    except: return None

def get_session_type(dt):
    """Returns 'Morning' or 'Evening' based on the hour."""
    return "Morning" if dt.hour < 12 else "Evening"

def convert_to_et(utc_dt):
    et_zone = pytz.timezone('US/Eastern')
    if utc_dt.tzinfo is None: utc_dt = utc_dt.replace(tzinfo=utc)
    return utc_dt.astimezone(et_zone)

def get_compass_direction(degrees):
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    return directions[int((degrees + 22.5) % 360 // 45)]

# --- MAIN EXECUTION ---

def main():
    # 1. Handle Arguments (Address, Zip, and optional Days)
    if len(sys.argv) < 3:
        print("Usage: python iss_tracker.py \"Street Address\" \"Zip\" [DaysToSearch]")
        return

    street = sys.argv[1]
    zip_code = sys.argv[2]
    # Default to 7 days if the user doesn't provide a third argument
    search_days = int(sys.argv[3]) if len(sys.argv) > 3 else 7

    coords = get_coords(street, zip_code)
    if not coords: return print("Address not found.")
    
    lat, lon = coords
    ts = load.timescale()
    planets = load('de421.bsp')
    sun, earth = planets['sun'], planets['earth']
    
    # Load ISS orbital data
    stations_url = 'http://celestrak.org/NORAD/elements/stations.txt'
    satellites = load.tle_file(stations_url)
    iss = {sat.name: sat for sat in satellites}['ISS (ZARYA)']
    home = wgs84.latlon(lat, lon)

    print(f"\nSearching next {search_days} days for visible passes at {street}...")
    print(f"{'Date':<12} | {'Time (ET)':<12} | {'Elev':<6} | {'Dir':<5} | {'Session'}")
    print("-" * 65)

    start_time = datetime.utcnow().replace(tzinfo=utc)
    found_any = False
    
    # Process in 3-day chunks to be efficient
    for chunk in range(0, search_days, 3):
        t0 = ts.from_datetime(start_time + timedelta(days=chunk))
        # Don't search past the user's requested limit
        end_offset = min(chunk + 3, search_days)
        t1 = ts.from_datetime(start_time + timedelta(days=end_offset))

        t, events = iss.find_events(home, t0, t1, altitude_degrees=20.0)

        for ti, event in zip(t, events):
            if event == 1: # Peak
                is_sunlit = iss.at(ti).is_sunlit(planets)
                observer = earth + home
                sun_alt = observer.at(ti).observe(sun).apparent().altaz()[0].degrees
                
                # Visibility logic: ISS in sun, Ground in dark
                if is_sunlit and sun_alt < -6:
                    diff = iss - home
                    alt, az, dist = diff.at(ti).altaz()
                    
                    local_dt = convert_to_et(ti.utc_datetime())
                    date_str = local_dt.strftime('%m/%d/%Y')
                    time_str = local_dt.strftime('%I:%M %p')
                    session = get_session_type(local_dt)
                    compass = get_compass_direction(az.degrees)
                    
                    print(f"{date_str:<12} | {time_str:<12} | {alt.degrees:>2.0f}°   | {compass:<5} | {session}")
                    found_any = True

    if not found_any:
        print(f"No visible passes found in the next {search_days} days.")
    print("-" * 65)

if __name__ == "__main__":
    main()