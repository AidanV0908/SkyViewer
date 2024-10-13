# Reference: https://rhodesmill.org/skyfield/earth-satellites.html
#!/usr/bin/env python3

import skyfield.elementslib
from skyfield.api import wgs84, load, EarthSatellite
import math
import skyfield.timelib
from flask import Flask, request, jsonify, render_template
import requests
import os;
import openai
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from skyfield.api import utc
import threading;

import numpy as np;
import matplotlib
import matplotlib.pyplot as plt
import time
from config import VERSION, DATE, API_URL, HEADERS, MAX_CACHE_TIME, MU, RE_EQ, T_PROP_MAX
import json
from matplotlib.lines import Line2D

import redis
from redis.commands.json.path import Path
import redis.commands.search.aggregation as aggregations
import redis.commands.search.reducers as reducers
from redis.commands.search.field import TextField, NumericField, TagField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import NumericFilter, Query
from redis.exceptions import RedisError

matplotlib.use('agg')


load_dotenv()

app = Flask(__name__)

# GET OPENAI KEY
openai.api_key = os.getenv("OPENAI_API_KEY")

# GET REDIS URL
# REDIS_URL = os.getenv("REDIS_URL")

# SET UP REDIS CACHE
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # or however long you want the session to last

r = redis.Redis(
        host=os.getenv("REDIS_HOST"),
        port=int(os.getenv("REDIS_PORT")), 
        db=int(os.getenv("REDIS_DB")), 
        username = os.getenv("REDIS_USER"),
        password = os.getenv("REDIS_PASS")
    )

# Calls home screen, caches default search
@app.route("/")
def SkyViewer():
    # Start caching asynchronously in a separate thread
    threading.Thread(target=cache_default).start()
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

# Launches observation page
@app.route("/get-obs-info", methods=['POST'])
def get_obs_info():
    # Get and pass on satellite ID from JSON
    satellite_id = request.form.get("ID")
    # Get satellite data
    data = json.loads(r.get(f"{satellite_id}"))
    # Extract epoch
    epoch_date = data['epoch_date']

    return render_template('obsdata.html',
                        satellite_id=satellite_id,
                        epoch_date = epoch_date)


# Launches results page
@app.route("/results", methods=['GET'])
def get_results():
    # Get satellite ID
    satelliteId = request.args.get('satelliteId')

    # data = get_sat_data(satelliteId)

    return render_template('results.html')

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

# Endpoint to check and cache satellite id
@app.route('/add-satellite-to-cache', methods=['POST'])
def cache_sat():
    data = request.json  # Use request.json to get JSON data
    id = data.get("ID")
    # Make an API request to fetch sorted results based on the search term
    api_url = f"{API_URL}/{id}"
    response = requests.get(api_url, headers=HEADERS)
    
    if response.status_code == 200:
        data = response.json()
        # Get information from JSON
        name = data['name']
        line1 = data['line1']
        line2 = data['line2']
        # Get epoch date from TLE
        epoch = parse_tle_epoch(line1)
        # Calculate difference between current time and epoch time
        now = datetime.now(timezone.utc)
        t_diff = (now - epoch).days
        # Create JSON for satellite. Include epoch as a commonly referenced value
        satellite = {
            "name" : name,
            "line1" : line1,
            "line2" : line2,
            "epoch_date" : epoch.strftime("%Y-%m-%d"),
            "epoch_time" : epoch.strftime("%H-%M-%S")
        }
        # Try to cache the satellite
        try:
            r.set(f"{id}", json.dumps(satellite))
            return jsonify({'message': 'Data saved to cache successfully', 'days_since_epoch': t_diff, 'maxprop': T_PROP_MAX}), 200
        except RedisError as e:
            # Log the error (optional) and return an error response
            print(f"Error saving to Redis: {e}")
            return jsonify({'error': 'CachingFailure'}), 503  # 503 Service Unavailable
    
    return jsonify({'error': 'Failure of NASA API'}), 503  # 503 Service Unavailable

# Endpoint to check and cache satellite id
@app.route('/remove-satellite-from-cache', methods=['POST'])
def remove_id_from_cache():
    data = request.json  # Use request.json to get JSON data
    satellite_id = data.get("ID")
    
    if not satellite_id:
        return jsonify({'error': 'ID is required in the request body'}), 400  # Bad Request if ID is missing

    response = r.delete(f"{satellite_id}")

    if response==1:
        # Log the error (optional) and return an error response
        return jsonify({'message': 'Successfully removed key'}), 200 
    else:
        return jsonify({'warning': 'Failed to remove key from cache'}), 503  # 503 Service Unavailable
    

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

    # Check if data is cached
    cache_key = f"{search_term}_{page}"
    
    cached_data = r.get(cache_key)
    if cached_data:
        return (json.loads(cached_data))
    
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
    
    r.set(f"{search_term}_{page}", json.dumps(data), ex=MAX_CACHE_TIME)
    return data

# Get data from specific TLE data
def get_sat_data(satelliteId, date, time_in, tz, lat_observer_obs, long_observer_obs):
    # Default calculated output variable states -- if not found
    az = alt = distance = epoch = classification = ai_exerpt = name = "<Missing>"
    sma = inc = raan = argp = ea = ecc = "<Missing>"
    obs_time_jd = obs_time_utc = time_tz = '<Missing>'

    # Get TLE data
    # api_url = f"{API_URL}/{satelliteId}"
    # response = requests.get(api_url, headers=HEADERS)
    # if response.status_code == 200:

    # Get cached data from ID
    data = json.loads(r.get(f"{satelliteId}"))
    
    name = data['name']

    # Get AI exerpt
    try:
        PROMPT = f"Generate a brief exerpt (100 - 150 words) about the satellite {name}. Include the creators (orgs and countries), mission plan, accomplishments and results if applicable, and interesting facts."
        response = comp(PROMPT)
        ai_exerpt = response.choices[0].message.content
    except:
        ai_exerpt = "I have been drained of OpenAI API tokens and I'm not trying to spend a fortune on this. AI exerpt unavailable, for now."

    # Skyfield stuff
    line1 = data['line1']
    line2 = data['line2']

    launch_year = int(line1[9:11])
    year = ''
    if launch_year < 57:
        year = str(launch_year + 2000)
    else:
        year = str(launch_year + 1900)

    ts = load.timescale()
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
    period = 2*np.pi*np.sqrt(np.pow(sma, 3) / MU)

    # Parse the date and time separately
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    time_obj = datetime.strptime(time_in, "%H:%M:%S").time()

    # Set timezone to UTC, or another specific offset
    tz_info = timezone(timedelta(hours=float(tz)))
    obs_datetime = datetime.combine(date_obj, time_obj, tzinfo=tz_info)
    time_tz = obs_datetime.strftime("%H:%M:%S")

    # Skyfield times
    ts = load.timescale()
    obs_t = ts.from_datetime(obs_datetime)
    obs_time_jd = str((obs_t.J  - 2000.0) * 365.25 + 2451545)
    epoch_jd = str((satellite.epoch.J - 2000) * 365.25 + 2451545)
    obs_time_utc = obs_t.utc_iso()
    epoch_utc = satellite.epoch.utc_iso()

    # Difference between epoch and observation time in days
    t_diff = abs(obs_t - satellite.epoch)

    # DO NOT PROPAGATE past a month, too many steps & accuracy decrease causes it to not be worth it
    if (t_diff < 30):
        # Get steps
        steps = np.ceil(steps_per_day(sma - RE_EQ) * t_diff)

        # Get a list of times between epoch and observation time to propagate
        propagations = ts.linspace(satellite.epoch, obs_t, 1000)

        # Get the states at all of the propagation times
        sat_states = satellite.at(propagations)
        lats_prop, longs_prop = wgs84.latlon_of(sat_states)

        # Generate ground track plot if observation time is within propagation window
        plt.figure()
        img = plt.imread('static/images/Map.jpg')
        plt.imshow(img, extent=[-180, 180, -90, 90])

        # Split ground track into segments for wrapping at map edges
        segments = []
        segment_start = 0
        # Get longitudes in degrees
        longs_prop = longs_prop.degrees
        lats_prop = lats_prop.degrees
        for i in range(1, len(longs_prop)):
            if abs(longs_prop[i] - longs_prop[i - 1]) > 180:
                segments.append((longs_prop[segment_start:i], lats_prop[segment_start:i]))
                segment_start = i
        # Append the last segment
        segments.append((longs_prop[segment_start:], lats_prop[segment_start:]))

        # Plot each segment separately
        for long_segment, lat_segment in segments:
            plt.plot(long_segment, lat_segment, color="olive", markersize=1)

        # Fake line to represent all plots of ground track in one legend entry
        # custom_line = Line2D([0], [0], color='olive', lw=1)

        # Plot user location
        # observer = plt.plot(float(long_observer_obs), float(lat_observer_obs), marker="*", color="b", markersize=5)

        # Plot epoch
        # lat_epoch, long_epoch = lats_prop[0], longs_prop[0]
        # epoch = plt.plot(float(long_epoch), float(lat_epoch), marker="o", color="g", markersize=5)

        # Plot satellite at obs time
        # lat_sat_obs, long_sat_obs = lats_prop[len(lats_prop) - 1], longs_prop[len(longs_prop) - 1]
        # sat_obs = plt.plot(float(long_sat_obs), float(lat_sat_obs), marker="o", color="r", markersize=5)

        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.xlim(-180, 180)
        plt.ylim(-90, 90)
        plt.title(f'{name} Ground Track')
        # plt.legend(
            # handles=[custom_line, observer, epoch, sat_obs],
            # labels=["Ground Track", "Observer", "Sat@Epoch", "Sat@Obs"]
        # )
        plt.grid(True)
        timestamp = int(time.time())
        path = os.path.join('static', 'images', 'GT.png')
        plt.savefig(path)
        plt.close()

        # Get the observer location from their latitude and longitude
        obs_loc = wgs84.latlon(float(lat_observer_obs), float(long_observer_obs))

        # Get the satellite info relative to the observer at the observation time
        difference = satellite - obs_loc
        topocentric = difference.at(obs_t)
        alt, az, distance = topocentric.altaz()
        az = az.degrees
        alt = alt.degrees
        distance = distance.km
        
    return {
        "satelliteName" : name,
        "satelliteId" : satelliteId,
        "date" : date,
        "time" : time_in,
        "timezone" : tz,
        "latitude" : lat_observer_obs,
        "longitude" : long_observer_obs,
        "ai_exerpt" : ai_exerpt,
        "launch_year" : year,
        "period" : period,
        "alt" : alt,
        "az" : az,
        "distance" : distance,
        "sma" : sma,
        "inc" : inc,
        "raan" : raan,
        "epoch" : epoch_utc,
        "obs_time_jd" : obs_time_jd,
        "obs_time_utc" : obs_time_utc,
        "ecc" : ecc,
        "argp" : argp,
        "timestamp" : timestamp,
        "classification" : classification,
        "time_tz" : time_tz,
    }

# Function to cache default search
def cache_default():
    search_TLE('ISS', 1)

# Returns the amount of ground track steps to do per day
def steps_per_day(altitude):
    # Parameters for the continuous function
    base_steps = 96  # Base steps per day for very low altitudes (e.g., close to Earth's surface)
    scaling_factor = 2000  # Controls how quickly the steps decrease with altitude
    
    # Continuous function: Inverse relationship with altitude
    steps_per_day = base_steps / (1 + altitude / scaling_factor)
    
    # Ensure a minimum of 6 steps per day for high altitudes
    steps_per_day = max(steps_per_day, 6)
    
    return round(steps_per_day)

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
