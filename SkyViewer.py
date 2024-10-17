# Reference: https://rhodesmill.org/skyfield/earth-satellites.html
#!/usr/bin/env python3

import skyfield.elementslib
from skyfield.api import wgs84, load, EarthSatellite, Topos
import math
import skyfield.timelib
from flask import Flask, request, jsonify, render_template
import requests
import os;
import openai
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from skyfield.api import utc

import numpy as np;
import time
from config import VERSION, DATE, API_URL, HEADERS, MU, RE_EQ, T_PROP_MAX


load_dotenv()

app = Flask(__name__)

# GET OPENAI KEY
openai.api_key = os.getenv("OPENAI_API_KEY")

# Calls home screen, caches default search
@app.route("/")
def SkyViewer():
    # Load startup page
    return render_template('startup.html')

# Loads the usage guide
@app.route("/usage-guide")
def info():
    return render_template('usageguide.html')

# Launches search page
@app.route("/sat-search", methods=['GET', 'POST'])
def search():
    # Set default values for search_term and page
    search_term = request.form.get('search_term', 'ISS')  # Default to ISS
    page = request.form.get('page', 1, type=int)       # Default to page 1

    # Make an API request to fetch sorted results based on the search term
    data = search_TLE(search_term, page)

    # Run search with initial (empty search) TLE data
    return render_template('search.html', **data)

# Propagation guide
@app.route('/propagation-restrictions')
def prop():
    return render_template('propagation.html')

# Launches results page
@app.route("/results", methods=['GET'])
def get_results():
    # Get satellite ID
    satelliteId = request.args.get('satelliteId')

    data = get_sat_data(satelliteId)

    if (data['code'] == 200):
        return render_template('results.html', **data)
    else:
        return render_template('404.html')

# Endpoint for search function to update results
@app.route("/refresh-search", methods=['POST'])
def update_search():
    search_term = request.json.get('search_term', 'ISS')  # Get search term from JSON payload
    page = request.json.get('page', 1)  # Default to page 1

    # Call TLE to fetch the data
    data = search_TLE(search_term, page)

    # Return the data as JSON
    return jsonify(data)

# Endpoint for version info
@app.route('/api/version', methods=['GET'])
def get_version():
    return jsonify({
        'version': VERSION,
        'date' : DATE,
    })

# Endpoint for maximum propagation time
@app.route('/prop-time', methods=['GET'])
def max_prop():
    return jsonify({
        'maxprop': T_PROP_MAX,
    })
    
# Endpoint for getting epoch data
@app.route('/epoch-data', methods=['POST'])
def epoch_data():
    datain = request.json  # Use request.json to get JSON data
    id = datain.get("ID")

    api_url = f"{API_URL}/{id}"
    response = requests.get(api_url, headers=HEADERS)
    
    if response.status_code == 200:
        data = response.json()
        line1 = data['line1']
        # Get epoch date from TLE
        epoch_datetime = parse_tle_epoch(line1)

        # Get the dates T_PROP_MAX before epoch and after epoch
        date_before = epoch_datetime - timedelta(days=T_PROP_MAX)
        date_after = epoch_datetime + timedelta(days=T_PROP_MAX)

        # Convert back to string format "YYYY-MM-DD"
        prop_min = date_before.strftime("%Y-%m-%d")
        prop_max = date_after.strftime("%Y-%m-%d")

        # Check if the current date is within the propagation bounds
        now_datetime = datetime.now(timezone.utc)

        # Get difference between current time and epoch
        dt = (now_datetime - epoch_datetime).days

        return jsonify({
            'maxprop': T_PROP_MAX,
            'days_since_epoch' : dt,
            'prop_min' : prop_min,
            'prop_max' : prop_max
        })
    
    return { "message" : "Couldn't get satellite info" }, 503

# Endpoint for maximum propagation time
@app.route('/generate-gt', methods=['POST'])
def generate_ground_track():
    datain = request.json  # Use request.json to get JSON data
    # ID of satellite
    id = datain.get("ID")
    # Reference date and time for ground track
    refD = datain.get("date")
    refT = datain.get("time")
    # Time zone of reference time
    refTZ = datain.get("timezone")
    # Number of periods to show on ground track
    periods = int(datain.get("periods"))
    # Direction of propagation ("forward" "backward" "bidirectional")
    direction = datain.get("direction")
    # Observation latitude and longitude
    obslat = datain.get("lat")
    obslong = datain.get("long")

    api_url = f"{API_URL}/{id}"
    response = requests.get(api_url, headers=HEADERS)
    
    if response.status_code == 200:
        data = response.json()
        name = data['name']
        line1 = data['line1']
        line2 = data['line2']

        satellite = EarthSatellite(line1, line2, name)

        # Get t_start and t_end from reference time
        sat_state = satellite.at(satellite.epoch)
        orbit = skyfield.elementslib.osculating_elements_of(sat_state)
        sma = orbit.semi_major_axis.km
        period = 2*np.pi*np.sqrt(np.pow(sma, 3) / MU) # s
        refTime = datetime.strptime(f"{refD} {refT}", "%Y-%m-%d %H:%M:%S")

        # Add timezone
        utc_offset_hours = int(refTZ)
        utc_offset = timezone(timedelta(hours=utc_offset_hours))
        refTime = refTime.replace(tzinfo = utc_offset)
        refTime = refTime.astimezone(timezone.utc)
        
        print(refTime)

        # Get start and end times
        startTime = stopTime = refTime
        if (direction == "forward"):
            stopTime = refTime + timedelta(seconds=period*periods)
        elif (direction == "backward"):
            startTime = refTime - timedelta(seconds=period*periods)
        else:
            startTime = refTime - timedelta(seconds=period*(periods/2))
            stopTime = refTime + timedelta(seconds=period*(periods/2))

        # Calculate steps to use
        dt = (period*periods) / (3600*24)
        step_count = steps(sma - RE_EQ, dt)

        # Get latitudes and longitudes
        ts = load.timescale()
        t_start = ts.from_datetime(startTime)
        t_stop = ts.from_datetime(stopTime)
        stepTimes = ts.linspace(t_start, t_stop, step_count)

        sat_states = satellite.at(stepTimes)
        lats_prop, longs_prop = wgs84.latlon_of(sat_states)

        lats_prop = lats_prop.degrees
        longs_prop = longs_prop.degrees

        # Get latitude and longitude of refTime
        refTime_t = ts.from_datetime(refTime)
        lat_ref, long_ref = wgs84.latlon_of(satellite.at(refTime_t))

        print(f"({lat_ref.degrees}, {long_ref.degrees})")

        # Prepare data for JSON response
        response_data = {
            'latitudes': lats_prop.tolist(),
            'longitudes': longs_prop.tolist(),
            'name': name,
            'observerLat': float(obslat),
            'observerLong': float(obslong),
            'timestamp': time.time(),
            'refLat' : float(lat_ref.degrees),
            'refLong' : float(long_ref.degrees),
            "pathColor" : datain.get("pathColor"),
            "observerColor" : datain.get("observerColor"),
            "refTimeColor" : datain.get("refTimeColor"),
        }

        return response_data, 200
    
    return { "message" : "Couldn't get satellite info" }, 503

# Check sunlit status
@app.route('/is-sunlit', methods=['POST'])
def sunlit():
    datain = request.json  # Use request.json to get JSON data
    # ID of satellite
    id = datain.get("ID")
    # Reference date and time for ground track
    date = datain.get("date")
    time = datain.get("time")
    tz = datain.get("tz")
   
    # Ephemeris
    eph = load('de421.bsp')

    api_url = f"{API_URL}/{id}"
    response = requests.get(api_url, headers=HEADERS)
    
    if response.status_code == 200:
        data = response.json()
        name = data['name']
        line1 = data['line1']
        line2 = data['line2']

        satellite = EarthSatellite(line1, line2, name)

        t = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M:%S")
        utc_offset_hours = float(tz)
        utc_offset = timezone(timedelta(hours=utc_offset_hours))
        t = t.replace(tzinfo = utc_offset)
        t = t.astimezone(timezone.utc)

        ts = load.timescale()
        t = ts.from_datetime(t)

        sat_state = satellite.at(t)

        is_sun = sat_state.is_sunlit(eph)

        sunStatus = "idk"
        if (is_sun):
            sunStatus = "be sunlit"
        else:
            sunStatus = "not be sunlit"

        # Prepare data for JSON response
        response_data = {
            'satelliteName': name,
            'sunStatus': sunStatus,
        }

        return response_data, 200
    
    return { "message" : "Couldn't get satellite info" }, 503

# Find next pass
@app.route('/next-pass', methods=['POST'])
def nextPass():
    datain = request.json  # Use request.json to get JSON data
    # ID of satellite
    id = datain.get("ID")

    # Observation latitude and longitude
    obslat = datain.get("lat")
    obslong = datain.get("long")
    min_elevation = datain.get("minEl")

    api_url = f"{API_URL}/{id}"
    response = requests.get(api_url, headers=HEADERS)
    
    if response.status_code == 200:
        data = response.json()
        name = data['name']
        line1 = data['line1']
        line2 = data['line2']

        satellite = EarthSatellite(line1, line2, name)


        ts = load.timescale()
        start_time = ts.utc(datetime.now().replace(tzinfo=timezone.utc))
        end_time = start_time + timedelta(days=1)

        observer_location = Topos(float(obslat), float(obslong))  # Example for West Lafayette, IN

        t, events = satellite.find_events(observer_location, start_time, end_time, altitude_degrees=min_elevation)

        timezone_offset = timedelta(hours=float(datain.get("tz")))

        message = "All times are in stated reference time zone. If nothing appears, no next passes were found within 24 hours.\n"
        for ti, event in zip(t, events):
            # Get UTC hour, minute, and second
            local_time = ti.utc_datetime() + timezone_offset
            hours, minutes = local_time.hour, local_time.minute
            seconds = round(local_time.second)

            # Format as HH:MM:SS
            ft = f"{hours:02}:{minutes:02}:{seconds:02}"

            if event == 0:
                message += f"At {ft}, the satellite will rise above {min_elevation}.\n"
            elif event == 1:
                message += f"At {ft}, the satellite will reach its maximum elevation angle.\n"
            else:
                message += f"At {ft}, the satellite will fall below {min_elevation}.\n"


        # Prepare data for JSON response
        response_data = {
            'message': message,
        }

        return response_data, 200
    
    return { "message" : "Couldn't get satellite info" }, 503


# function that takes in string argument as parameter
def comp(PROMPT):
    # using OpenAI's Completion module that helps execute
    # any tasks involving text
    response = openai.chat.completions.create(
        # model name used here is text-davinci-003
        # there are many other models available under the
        # umbrella of GPT-3
        model="gpt-3.5-turbo-0125",
        # passing the user input
        messages = [
            {"role" : "user", "content" : PROMPT}
        ]
    )

    return response

# Get TLE search info from API
def search_TLE(search_term, page):
    # Results per page (fixed at 20 by output of API)
    per_page =  20

    # Make an API request to fetch sorted results based on the search term
    api_url = f"{API_URL}?search={search_term}&page={page}"
    response = requests.get(api_url, headers=HEADERS)

    # Placeholder
    members = []
    total_results = 0
    
    # If successful, get data, 
    if response.status_code == 200:
        data = response.json()  # Assuming the API returns JSON data
        members = data.get('member', [])  # Get the 'member' array from the response
        total_results = data['totalItems']
        # Override for total items due to a weird error in API for single-item searches
        if (len(members) < 20 and page == 1):
            total_results = len(members)

    # Determine if we need to show next/prev buttons
    has_next = total_results > page * per_page
    has_prev = page > 1

    # pages
    pages = math.ceil(total_results / 20)

    data = { 
            'search_term' : search_term,
            'page' : page,
            'members': members,
            'total_results' : total_results,
            'pages': pages,
            'has_prev': has_prev,
            'has_next': has_next,
            'API_Code': response.status_code 
            }
    
    return data

# Get data from specific TLE data
def get_sat_data(satelliteId):
    # Get TLE data
    api_url = f"{API_URL}/{satelliteId}"
    response = requests.get(api_url, headers=HEADERS)

    code = response.status_code
    
    if response.status_code == 200:
        data = response.json()
        name = data['name']

        # Get AI exerpt
        try:
            PROMPT = f"Generate a brief exerpt (100 - 150 words) about the satellite {name}. Include the creators (orgs and countries), mission plan, accomplishments and results if applicable, and interesting facts."
            response = comp(PROMPT)
            ai_exerpt = response.choices[0].message.content
        except:
            ai_exerpt = "AI exerpt generation failed. Try again later."

        # Skyfield stuff
        line1 = data['line1']
        line2 = data['line2']

        launch_year = int(line1[9:11])
        year = ''
        if launch_year < 57:
            year = str(launch_year + 2000)
        else:
            year = str(launch_year + 1900)

        satellite = EarthSatellite(line1, line2, name)
        classifications = {
            "U": "Unclassified",
            "C": "Classified",
            "S": "Secret"
        }
        classification = classifications.get(satellite.model.classification, "Unknown")

        # Orbit elements (epoch)
        sat_state = satellite.at(satellite.epoch)
        orbit = skyfield.elementslib.osculating_elements_of(sat_state)
        sma = orbit.semi_major_axis.km
        ecc = orbit.eccentricity
        inc = orbit.inclination.degrees
        raan = orbit.longitude_of_ascending_node.degrees
        argp = orbit.argument_of_periapsis.degrees
        period = 2*np.pi*np.sqrt(np.pow(sma, 3) / MU) # s

        # Epoch time representations
        epoch_jd = str((satellite.epoch.J - 2000) * 365.25 + 2451545)
        epoch_utc = satellite.epoch.utc_iso()

        # Convert to a datetime
        epoch_datetime = datetime.fromisoformat(epoch_utc.replace("Z", ""))

        # Format it to only display the date
        epoch_date = epoch_datetime.strftime("%Y-%m-%d")
        epoch_time = epoch_datetime.strftime("%H:%M:%S")

        return {
            "code" : code,
            "satelliteName" : name,
            "satelliteId" : satelliteId,
            "ai_exerpt" : ai_exerpt,
            "launch_year" : year,
            "period" : f"{(period / 3600):.4f}",
            "sma" : f"{sma:.4f}",
            "inc" : f"{inc:.4f}",
            "raan" : f"{raan:.4f}",
            "epochdate" : epoch_date,
            "epochtime" : epoch_time,
            "ecc" : f"{ecc:.4f}",
            "argp" : f"{argp:.4f}",
            "maxprop" : T_PROP_MAX,
            "classification" : classification,
        }
    else:
        return { "code" : code }

# Returns the amount of ground track steps to do per day
def steps(altitude, deltaTime):
    # Parameters for the continuous function
    base_steps = 96  # Base steps per day for very low altitudes (e.g., close to Earth's surface)
    scaling_factor = 2000  # Controls how quickly the steps decrease with altitude
    
    # Continuous function: Inverse relationship with altitude
    steps_per_day = base_steps / (1 + altitude / scaling_factor)
    
    # Ensure a minimum of 6 steps per day for high altitudes
    steps_per_day = max(steps_per_day, 6)
    
    return 1000
    #return round(steps_per_day * deltaTime)

# Get epoch from TLE line 1 (returns a datetime)
def parse_tle_epoch(tle_line1):
    # Extract the year and day of year from the TLE epoch field
    year = int(tle_line1[18:20])
    day_of_year = float(tle_line1[20:32])

    # Convert two-digit year to four digits (assume 2000s for simplicity)
    year += 2000 if year < 57 else 1900  # Assume 57+ as 1957+ and below as 2000+

    # Separate the integer and fractional parts of day_of_year
    day_integer = int(day_of_year)
    day_fraction = day_of_year - day_integer

    # Create the base date for the year and add days
    epoch = datetime(year, 1, 1) + timedelta(days=day_integer - 1)  # -1 since Jan 1 is day 1

    # Add the fractional day component as seconds
    epoch += timedelta(seconds=day_fraction * 86400)  # 86400 seconds in a day

    return epoch.replace(tzinfo=timezone.utc)
