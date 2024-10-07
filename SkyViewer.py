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

load_dotenv()

os.environ['OPENAI_API_KEY'] = os.getenv("OPENAI_API_KEY")
openai.api_key = os.environ['OPENAI_API_KEY']
NASA_API_KEY = os.environ['NASA_API_KEY']

app = Flask(__name__)

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
    return render_template('startup.html')

@app.route("/usage-guide")
def info():
    return render_template('usageguide.html')

@app.route("/sat-search", methods=['GET', 'POST'])
def search():
    # Get the search term and page number from the URL
    page = request.args.get('page', 1, type=int)  # Default to page 1 if not provided
    search_term = request.args.get('search_term', '')  # Default to empty string if not provided
    API_Code = 200

    per_page = 20

    if request.method == 'POST':
        # Get the search term from the form
        search_term = request.form['search_term']

    # Make an API request to fetch sorted results based on the search term
    if (search_term != ''):
        api_url = f"{API_URL}?search={search_term}&page={page}"
        response = requests.get(api_url, headers=headers)

        if response.status_code == 200:
            data = response.json()  # Assuming the API returns JSON data
            members = data.get('member', [])  # Get the 'member' array from the response
            total_results = data['totalItems']
            pages = math.ceil(total_results / 20)
        else:
            members = []
            total_results = 0
            pages = 1
            API_Code = response.status_code

    else:
        members = []
        total_results = 0
        pages = 1

    # Determine if we need to show next/prev buttons
    has_next = total_results > page * per_page
    has_prev = page > 1

    # pages
    pages = math.ceil(total_results / 20)

    return render_template('search.html',
                           search_term=search_term,
                           num_results = total_results,
                           members = members,
                           page = page,
                           pages = pages,
                           has_prev = has_prev,
                           has_next = has_next,
                           API_Code = API_Code)

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
    timezone = request.args.get('timezone', '0')
    latitude = request.args.get('latitude', '<Missing>')
    longitude = request.args.get('longitude', '<Missing>')
    # Default calculated output variable states -- if not found
    az = alt = distance = epoch = classification = ai_exerpt = name = "<Missing>"
    sma = inc = raan = argp = ea = ecc = "<Missing>"
    obs_time_jd = obs_time_utc = time_tz = '<Missing>'
    is_obs = False
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
            ai_exerpt = "I have been drained of API tokens and I'm not trying to spend a fortune on this. Try again next month."
        # Run skyfield calculations
        line1 = data['line1']
        line2 = data['line2']
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
        sat_pos = satellite.at(satellite.epoch)
        orbit = skyfield.elementslib.osculating_elements_of(sat_pos)
        sma = orbit.semi_major_axis.m
        ecc = orbit.eccentricity
        inc = orbit.inclination.degrees
        raan = orbit.longitude_of_ascending_node.degrees
        argp = orbit.argument_of_periapsis.degrees
        # Confirm form submitted and get observation data
        if (date != '<Missing>'):
            is_obs = True

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
    else:
        ai_exerpt = "Unable to generate -- missing satellite information"

    return render_template('results.html',
                    satelliteName = name,
                    satelliteId = satelliteId,
                    date = date,
                    time = time,
                    timezone = timezone,
                    latitude = latitude,
                    longitude = longitude,
                    ai_exerpt = ai_exerpt,
                    alt = alt,
                    az = az,
                    distance = distance,
                    sma = sma,
                    inc = inc,
                    raan = raan,
                    epoch = epoch,
                    obs_time_jd = obs_time_jd,
                    obs_time_utc = obs_time_utc,
                    ecc = ecc,
                    argp = argp,
                    classification = classification,
                    time_tz = time_tz,
                    is_obs = is_obs)

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
