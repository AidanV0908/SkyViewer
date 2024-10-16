# VERSION INFO
VERSION = "1.0.0"
DATE = '16-OCT-2024'

# API INFO
API_URL = "http://tle.ivanstanojevic.me/api/tle"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Accept': 'application/json',  # Modify this depending on what the API expects
    'Connection': 'keep-alive'  # Keep the connection alive
}

# MU of Earth
MU = 398600.4418

# MJD TO JD
MJD_TO_JD = 2400000.5

# RADIUS OF EARTH
RE_EQ = 6378.137 

# MAXIMUM PROPAGATION TIME ALLOWED (days)
T_PROP_MAX = 30
