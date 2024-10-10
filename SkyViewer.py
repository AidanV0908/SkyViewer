# Reference: https://rhodesmill.org/skyfield/earth-satellites.html
#!/usr/bin/env python3

import skyfield.elementslib
from skyfield.api import wgs84, load, EarthSatellite
import sys
import math
import skyfield.timelib
from flask import Flask, request, jsonify, render_template, redirect
import requests
import os;
import openai
from dotenv import load_dotenv
from datetime import datetime, timedelta
from skyfield.api import utc
from flask_caching import Cache;
import threading;

import numpy as np;
from Propagator import propagator
from scipy import integrate
import matplotlib
import matplotlib.pyplot as plt
import Earth

matplotlib.use('agg')


load_dotenv()

os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
openai.api_key = os.environ['OPENAI_API_KEY']
NASA_API_KEY = os.environ['NASA_API_KEY']

# Version info
VERSION = "1.2.0"
DATE = '10-OCT-2024'

cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})

app = Flask(__name__)
cache.init_app(app)

# NASA API KEY
#NASA_API_KEY = os.environ['NASA_API_KEY']
# API endpoint (modify this to match the actual API you're using)
API_URL = "http://tle.ivanstanojevic.me/api/tle"  # Replace with your actual API endpoint

# API Headers
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Accept': 'application/json',  # Modify this depending on what the API expects
    'Connection': 'keep-alive'  # Keep the connection alive
}

@app.route("/")
def SkyViewer():
    # Start caching asynchronously in a separate thread
    threading.Thread(target=cache_default).start()
    # Load startup page
    return render_template('startup.html')

@app.route("/usage-guide")
def info():
    return render_template('usageguide.html')

@app.route("/sat-search", methods=['GET', 'POST'])
def search():
    # Set default values for search_term and page
    search_term = request.form.get('search_term', 'ISS')  # Default to ISS
    page = request.form.get('page', 1, type=int)       # Default to page 1

    # Make an API request to fetch sorted results based on the search term
    data = TLE(search_term, page)

    # Run search with initial (empty search) TLE data
    return render_template('search.html', **data)

@app.route("/get-obs-info", methods=['POST'])
def get_obs_info():
    # Get and pass on satellite ID
    satellite_id = request.form.get("selected_result")
    return render_template('obsdata.html',
                           satellite_id = satellite_id)

@app.route("/results", methods=['GET'])
def get_results():
    # Get satellite ID
    satelliteId = request.args.get('satelliteId')
    # Get observation data
    date = request.args.get('date', '<Missing>')
    time = request.args.get('time', '<Missing>')
    timezone = request.args.get('timezone', '<Missing>')
    latitude = request.args.get('latitude', '<Missing>')
    longitude = request.args.get('longitude', '<Missing>')

    data = get_sat_data(satelliteId, date, time, timezone, latitude, longitude)

    return render_template('results.html', **data)

# Endpoint so search function can update results
@app.route("/api/sat-search", methods=['POST'])
def update_search():
    search_term = request.json.get('search_term', '')  # Get search term from JSON payload
    page = request.json.get('page', 1)  # Default to page 1

    # Call TLE to fetch the data
    data = TLE(search_term, page)

    # Return the data as JSON
    return jsonify(data)

# Endpoint for getting version
@app.route('/api/version', methods=['GET'])
def get_constants():
    return jsonify({
        'version': VERSION,
        'date' : DATE,
    })

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

# Get TLE info from API
def TLE(search_term, page):
    # Results per page (fixed at 20 by output of API)
    per_page =  20

    # Check if data is cached
    cache_key = f"{search_term}_{page}"
    
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data
    
    # Make an API request to fetch sorted results based on the search term
    api_url = f"{API_URL}?search={search_term}&page={page}"
    response = requests.get(api_url, headers=headers)

    # Placeholder
    members = []
    total_results = 0
    
    # If successful, get data, 
    if response.status_code == 200:
        data = response.json()  # Assuming the API returns JSON data
        members = data.get('member', [])  # Get the 'member' array from the response
        total_results = data['totalItems']

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
    
    cache.set(f"{search_term}_{page}", data, timeout=60 * 5)
    return data

# Get data from specific TLE data
def get_sat_data(satelliteId, date, time, timezone, latitude, longitude):
    # Default calculated output variable states -- if not found
    az = alt = distance = epoch = classification = ai_exerpt = name = "<Missing>"
    sma = inc = raan = argp = ea = ecc = "<Missing>"
    obs_time_jd = obs_time_utc = time_tz = '<Missing>'

    # Get TLE data
    api_url = f"{API_URL}/{satelliteId}"
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        data = response.json()  # Assuming the API returns JSON data
        name = data['name']
        # Get AI exerpt
        try:
            PROMPT = f"Generate a brief exerpt (50 - 100 words) about the satellite {name}, ID {satelliteId} in the NORAD database. Do not restate the ID, that is for your reference."
            response = comp(PROMPT)
            ai_exerpt = response.choices[0].message.content
        except:
            ai_exerpt = "I have been drained of OpenAI API tokens and I'm not trying to spend a fortune on this. AI exerpt unavailable, for now."
        # Run skyfield calculations
        line1 = data['line1']
        line2 = data['line2']
        launch_year = year_str = line1[9:11]
        if (int(year_str) > int(str(datetime.now().year)[2:3])):
            launch_year = f"19{year_str}"
        else:
            launch_year = f"20{year_str}"
        ts = load.timescale()
        satellite = EarthSatellite(line1, line2, name)
        classifications = {
            "U": "Unclassified",
            "C": "Classified",
            "S": "Secret"
        }
        classification = classifications.get(satellite.model.classification, "Unknown")
        epoch = satellite.epoch.utc_iso()
        # Orbit elements (epoch)
        sat_state = satellite.at(satellite.epoch)
        orbit = skyfield.elementslib.osculating_elements_of(sat_state)
        sma = orbit.semi_major_axis.km
        ecc = orbit.eccentricity
        inc = orbit.inclination.degrees
        raan = orbit.longitude_of_ascending_node.degrees
        argp = orbit.argument_of_periapsis.degrees

        # Earth instance
        earth = Earth.earth()
        period = 2*np.pi*np.sqrt(np.pow(sma, 3) / earth.Mu())

        [y, m, d] = date.split('-')
        h = min = s = '00'
        try:
            [h, min, s] = time.split(':')
        except:
            [h, min] = time.split(':')


        time_tz = f"{h}:{min}:{s}"
        dt = datetime(int(y), int(m), int(d), int(h), int(min), int(s), tzinfo=utc) - timedelta(hours=float(timezone))

        obs_time = ts.utc(dt)
        obs_time_jd = obs_time.tdb
        obs_time_utc = obs_time.utc_strftime().split(" ")[1]

        obs_loc = wgs84.latlon(float(latitude), float(longitude))

        difference = satellite - obs_loc
        topocentric = difference.at(obs_time)
        alt, az, distance = topocentric.altaz()
        az = az.degrees
        alt = alt.degrees
        distance = distance.km

        # Get the ground track plot from propagated data and save it
        epoch_JD = satellite.epoch.tdb
        
        # Propagate
        prop_time = 3*period

        initial_cond = [sat_state.position.km[0], sat_state.position.km[1], sat_state.position.km[2], sat_state.velocity.km_per_s[0], sat_state.velocity.km_per_s[1], sat_state.velocity.km_per_s[2]]
        prop_data = propagate(initial_cond, (prop_time))

        GroundTrack(epoch_JD, prop_data, name)
    
    return {
        "satelliteName" : name,
        "satelliteId" : satelliteId,
        "date" : date,
        "time" : time,
        "timezone" : timezone,
        "latitude" : latitude,
        "longitude" : longitude,
        "ai_exerpt" : ai_exerpt,
        "launch_year" : launch_year,
        "period" : period,
        "alt" : alt,
        "az" : az,
        "distance" : distance,
        "sma" : sma,
        "inc" : inc,
        "raan" : raan,
        "epoch" : epoch,
        "obs_time_jd" : obs_time_jd,
        "obs_time_utc" : obs_time_utc,
        "ecc" : ecc,
        "argp" : argp,
        "classification" : classification,
        "time_tz" : time_tz,
    }

# Function to get ground track
def GroundTrack(epoch_JD, prop_data, name):
# Extract propagation data
    t = prop_data["t"]
    x = prop_data["x"]
    y = prop_data["y"]
    z = prop_data["z"]
    prop_len = len(t)

    # Initialize latitude and longitude arrays
    latitudes = np.zeros(prop_len)
    longitudes = np.zeros(prop_len)

    for i in range(prop_len):
        # Update time to Julian Date
        JD_current = epoch_JD + t[i] / (24 * 3600)
        
        # Convert ECI to ECEF
        M = M_ECI_to_ECEF(JD_current)
        pos_ECEF = M.dot(np.array([x[i], y[i], z[i]]))

        # Calculate latitude and longitude
        earth = Earth.earth()
        latitudes[i], longitudes[i] = earth.ecef_to_geodetic(pos_ECEF[0], pos_ECEF[1], pos_ECEF[2])

    # Wrap longitudes to stay within -180 to 180
    longitudes = np.mod((longitudes + 180), 360) - 180

    # Plot the ground track
    plt.figure()
    img = plt.imread('static/images/Map.jpg')
    plt.imshow(img, extent=[-180, 180, -90, 90])

    # Split ground track into segments for wrapping at map edges
    segments = []
    segment_start = 0
    for i in range(1, prop_len):
        if abs(longitudes[i] - longitudes[i - 1]) > 180:
            segments.append((longitudes[segment_start:i], latitudes[segment_start:i]))
            segment_start = i
    # Append the last segment
    segments.append((longitudes[segment_start:], latitudes[segment_start:]))

    # Plot each segment separately
    for long_segment, lat_segment in segments:
        plt.plot(long_segment, lat_segment, marker="o", color="red", markersize=1)

    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.xlim(-180, 180)
    plt.ylim(-90, 90)
    plt.title(f'{name} Ground Track')
    plt.grid(True)
    plt.savefig(os.path.join('static', 'images', 'GT.png'))
    plt.close()

# Updated M_ECI_to_ECEF function with improved sidereal time calculation
def M_ECI_to_ECEF(t_JD):
    # Julian century from J2000
    T = (t_JD - 2451545.0) / 36525.0
    
    # Greenwich Sidereal Time in degrees
    GMST = 280.46061837 + 360.98564736629 * (t_JD - 2451545.0) + 0.000387933 * T**2 - T**3 / 38710000.0
    GMST = np.mod(GMST, 360)

    # Convert to radians for rotation matrix
    theta = np.radians(GMST)
    return np.array([[np.cos(theta), -np.sin(theta), 0],
                     [np.sin(theta), np.cos(theta), 0],
                     [0, 0, 1]])

# Propagate function
def propagate(initial_cond, obs_time, t_steps = 1000):
    # Propogate
    p = integrate.solve_ivp(propagator, (0, obs_time), initial_cond, t_eval=np.linspace(0, obs_time, t_steps))
    t = p.t
    x, y, z = p.y[0], p.y[1], p.y[2]
    return { "t" : t, "x" : x, "y" : y, "z" : z }

# Function to cache default search
def cache_default():
    TLE('ISS', 1)