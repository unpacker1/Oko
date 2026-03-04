# ias4_global_full.py
import requests, datetime, math, logging, time, random
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO
from threading import Thread
from sgp4.api import Satrec, WGS72

# -------------------------------
# CONFIG
# -------------------------------
OPENWEATHER_API_KEY = "YOUR_OPENWEATHER_API_KEY"
AIS_HUB_API_KEY = "YOUR_AIS_HUB_API_KEY"
SPACE_TRACK_USERNAME = "YOUR_SPACE_TRACK_USERNAME"
SPACE_TRACK_PASSWORD = "YOUR_SPACE_TRACK_PASSWORD"

# Demo lokasyonlar
WEATHER_LOCATIONS = [
    {"name": "Istanbul", "lat": 41.0082, "lon": 28.9784},
    {"name": "London", "lat": 51.5074, "lon": -0.1278},
    {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
]

AIS_BOUNDING_BOX = "25,30,45,45"  # min_lat,min_lon,max_lat,max_lon

ROUTE_HISTORY_LIMIT = 30
SATELLITE_ROUTE_FORECAST_MINUTES = 30

# -------------------------------
# LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(msg):
    logging.info(msg)

# -------------------------------
# GLOBAL DATA
# -------------------------------
global_data = {
    "flights": [],
    "ships": [],
    "satellites": [],
    "weather": [],
    "flight_routes": {},
    "ship_routes": {},
    "satellite_routes": {},
    "last_update": None
}

space_track_session = None

# -------------------------------
# API FETCH FUNCTIONS
# -------------------------------
def fetch_weather_data():
    reports = []
    if OPENWEATHER_API_KEY == "YOUR_OPENWEATHER_API_KEY":
        return reports
    for loc in WEATHER_LOCATIONS:
        try:
            r = requests.get(
                "http://api.openweathermap.org/data/2.5/weather",
                params={"lat": loc["lat"], "lon": loc["lon"], "appid": OPENWEATHER_API_KEY, "units": "metric"},
                timeout=5
            )
            if r.status_code == 200:
                data = r.json()
                reports.append({
                    "name": loc["name"],
                    "latitude": loc["lat"],
                    "longitude": loc["lon"],
                    "temperature": data["main"]["temp"],
                    "description": data["weather"][0]["description"]
                })
        except:
            continue
    return reports

def fetch_ais_data():
    if AIS_HUB_API_KEY == "YOUR_AIS_HUB_API_KEY":
        return []
    min_lat, min_lon, max_lat, max_lon = map(float, AIS_BOUNDING_BOX.split(','))
    try:
        r = requests.get(f"http://data.aishub.net/ws.php?box={min_lon},{min_lat},{max_lon},{max_lat}&apiKey={AIS_HUB_API_KEY}&output=json", timeout=10)
        if r.status_code == 200:
            data = r.json()
            ships = []
            for s in (data.get('ships', []) if isinstance(data, dict) else data):
                try:
                    lat, lon = float(s.get('LAT',0)), float(s.get('LON',0))
                    if lat == 0 or lon == 0: continue
                    ships.append({
                        "mmsi": s.get("MMSI"),
                        "name": s.get("NAME", f"Ship-{s.get('MMSI')}"),
                        "latitude": lat,
                        "longitude": lon,
                        "speed": float(s.get("SOG",0)),
                        "course": float(s.get("COG",0))
                    })
                except: continue
            return ships
    except: return []
    return []

def fetch_opensky_data():
    try:
        r = requests.get("https://opensky-network.org/api/states/all", timeout=10)
        if r.status_code == 200:
            flights = []
            states = r.json().get("states",[])
            for f in states[:20]:  # sadece ilk 20 uçak demo
                flights.append({
                    "icao24": f[0],
                    "callsign": f[1].strip() if f[1] else "",
                    "longitude": f[5],
                    "latitude": f[6],
                    "altitude": f[7] or 10000,
                    "velocity": f[9] or 0
                })
            return flights
    except: pass
    return []

def login_space_track():
    global space_track_session
    if SPACE_TRACK_USERNAME == "YOUR_SPACE_TRACK_USERNAME": return None
    try:
        s = requests.Session()
        s.post("https://www.space-track.org/ajaxauth/login", data={'identity':SPACE_TRACK_USERNAME,'password':SPACE_TRACK_PASSWORD}, timeout=10)
        space_track_session = s
        return s
    except: return None

def fetch_satellite_tle_data():
    if not space_track_session: login_space_track()
    if not space_track_session: return []
    try:
        r = space_track_session.get("https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/format/json", timeout=10)
        data = r.json()
        sats = []
        for tle in data:
            sats.append({
                "norad_id": tle.get("NORAD_CAT_ID"),
                "name": tle.get("OBJECT_NAME"),
                "TLE_LINE1": tle.get("TLE_LINE1"),
                "TLE_LINE2": tle.get("TLE_LINE2")
            })
        return sats
    except: return []

def get_satellite_position_from_tle(line1,line2,time_obj):
    try:
        sat = Satrec.twoline2rv(line1,line2)
        jd = time_obj.timetuple().tm_yday + time_obj.hour/24
        e,r,v = sat.sgp4(time_obj.year,jd)
        if e==0:
            lon = math.degrees(r[0]%360)
            lat = math.degrees(r[1]%90)
            alt = r[2]
            return [lon,lat,alt]
    except: return None
    return None

# -------------------------------
# DATA PROCESSING
# -------------------------------
def update_routes(entity_list, key, route_dict, pos_func):
    current_ids = set()
    for e in entity_list:
        eid = e.get(key)
        if not eid: continue
        current_ids.add(eid)
        pos = pos_func(e)
        if not pos: continue
        if eid not in route_dict: route_dict[eid] = []
        route_dict[eid].append(pos)
        if len(route_dict[eid])>ROUTE_HISTORY_LIMIT: route_dict[eid].pop(0)
    # eski rotaları temizle
    for eid in list(route_dict.keys()):
        if eid not in current_ids: del route_dict[eid]
    return entity_list

def process_satellites(tle_data):
    processed = []
    now = datetime.datetime.utcnow()
    for t in tle_data[:5]: # demo sadece 5 uydu
        pos = get_satellite_position_from_tle(t["TLE_LINE1"],t["TLE_LINE2"],now)
        if pos:
            processed.append({"norad_id":t["norad_id"],"name":t["name"],"longitude":pos[0],"latitude":pos[1],"altitude":pos[2]})
    return processed

# -------------------------------
# LIVE DATA LOOP
# -------------------------------
def live_data_loop():
    while True:
        global_data["weather"] = fetch_weather_data()
        flights = fetch_opensky_data()
        global_data["flights"] = update_routes(flights,"icao24",global_data["flight_routes"],lambda f:[f["longitude"],f["latitude"],f["altitude"]])
        ships = fetch_ais_data()
        global_data["ships"] = update_routes(ships,"mmsi",global_data["ship_routes"],lambda s:[s["longitude"],s["latitude"],0])
        tles = fetch_satellite_tle_data()
        global_data["satellites"] = process_satellites(tles)
        global_data["last_update"] = datetime.datetime.utcnow().isoformat()
        time.sleep(10)

# -------------------------------
# FLASK + SOCKETIO
# -------------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>IAS4 Global</title>
    <script src="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Cesium.js"></script>
    <link href="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
    <style>body,html{margin:0;height:100%;}#cesiumContainer{width:100%;height:100%;}</style>
</head>
<body>
<div id="cesiumContainer"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
<script>
var viewer = new Cesium.Viewer('cesiumContainer',{
    imageryProvider: new Cesium.IonImageryProvider({assetId:2}), // Natural Earth
    baseLayerPicker:false,
    timeline:false,
    animation:false
});
var flightLayer = viewer.entities.add(new Cesium.Entity());
var shipLayer = viewer.entities.add(new Cesium.Entity());
var satelliteLayer = viewer.entities.add(new Cesium.Entity());

var socket = io();
socket.on('live_data', function(data){
    viewer.entities.removeAll();
    if(data.flights) data.flights.forEach(function(f){
        viewer.entities.add({name:f.callsign,position:Cesium.Cartesian3.fromDegrees(f.longitude,f.latitude,f.altitude/1000),point:{pixelSize:5,color:Cesium.Color.RED}});
    });
    if(data.ships) data.ships.forEach(function(s){
        viewer.entities.add({name:s.name,position:Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,0),point:{pixelSize:5,color:Cesium.Color.BLUE}});
    });
    if(data.satellites) data.satellites.forEach(function(s){
        viewer.entities.add({name:s.name,position:Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,s.altitude/1000),point:{pixelSize:5,color:Cesium.Color.GREEN}});
    });
});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/api/global_data")
def api_data():
    return jsonify(global_data)

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    Thread(target=live_data_loop,daemon=True).start()
    port = random.randint(8000,8999)
    log_event(f"Flask + SocketIO başlatılıyor port {port}")
    socketio.run(app, host="0.0.0.0", port=port)