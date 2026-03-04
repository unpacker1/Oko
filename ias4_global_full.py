# ias4_global_mobile.py
import requests, datetime, math, logging, time, os
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO
from sgp4.api import Satrec, WGS72
from threading import Thread

# -------------------------------
# CONFIG – Global Ayarlar
# -------------------------------
OPENWEATHER_API_KEY = "YOUR_OPENWEATHER_API_KEY"  # OpenWeatherMap API anahtarı
SPACE_TRACK_USERNAME = "YOUR_SPACE_TRACK_USERNAME"
SPACE_TRACK_PASSWORD = "YOUR_SPACE_TRACK_PASSWORD"
AIS_HUB_API_KEY = "YOUR_AIS_HUB_API_KEY"

WEATHER_LOCATIONS = [
    {"name": "Istanbul", "lat": 41.0082, "lon": 28.9784},
    {"name": "London", "lat": 51.5074, "lon": -0.1278},
    {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    {"name": "Cape Town", "lat": -33.9249, "lon": 18.4241},
    {"name": "Dubai", "lat": 25.276987, "lon": 55.296249},
    {"name": "Shanghai", "lat": 31.2304, "lon": 121.4737},
    {"name": "Rio de Janeiro", "lat": -22.9068, "lon": -43.1729}
]

AIS_BOUNDING_BOX = "-90,-180,90,180"  # Tüm dünya
ROUTE_HISTORY_LIMIT = 30
SATELLITE_ROUTE_FORECAST_MINUTES = 60

# -------------------------------
# LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("ias4_global.log"), logging.StreamHandler()])
def log_event(msg, level=logging.INFO):
    if level == logging.INFO:
        logging.info(msg)
    elif level == logging.ERROR:
        logging.error(msg)
    elif level == logging.WARNING:
        logging.warning(msg)

# -------------------------------
# GLOBAL DATA STORE
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
# DATA COLLECTION
# -------------------------------
def login_space_track(username, password):
    global space_track_session
    if not username or not password:
        log_event("Space-Track login atlanıyor", level=logging.WARNING)
        return None
    session = requests.Session()
    try:
        r = session.post("https://www.space-track.org/ajaxauth/login",
                         data={'identity': username, 'password': password}, timeout=10)
        if r.status_code == 200 and "Login Successful" in r.text:
            log_event("Space-Track login başarılı.")
            space_track_session = session
            return session
        space_track_session = None
    except:
        space_track_session = None
    return None

def fetch_weather_data():
    reports = []
    for loc in WEATHER_LOCATIONS:
        try:
            r = requests.get("http://api.openweathermap.org/data/2.5/weather",
                             params={"lat": loc["lat"], "lon": loc["lon"], "appid": OPENWEATHER_API_KEY, "units": "metric"}, timeout=5)
            if r.status_code == 200:
                data = r.json()
                reports.append({"name": loc["name"], "latitude": loc["lat"], "longitude": loc["lon"],
                                "temperature": data['main']['temp'], "description": data['weather'][0]['description']})
        except:
            continue
    return reports

def fetch_ais_data():
    min_lat, min_lon, max_lat, max_lon = map(float, AIS_BOUNDING_BOX.split(','))
    box_param = f"{min_lon},{min_lat},{max_lon},{max_lat}"
    try:
        r = requests.get("http://data.aishub.net/ws.php", params={"apikey": AIS_HUB_API_KEY,"box": box_param,"output":"json"}, timeout=15)
        ships_raw = r.json() if isinstance(r.json(), list) else r.json().get('ships', [])
        ships = []
        for s in ships_raw:
            try:
                lat, lon = float(s['LAT']), float(s['LON'])
                if lat == 0.0 or lon == 0.0: continue
                ships.append({'mmsi': s.get('MMSI'), 'name': s.get('NAME', f"Ship-{s.get('MMSI')}"),
                              'longitude': lon, 'latitude': lat, 'speed': float(s.get('SOG',0))})
            except: continue
        return ships
    except:
        return []

def fetch_opensky_data():
    try:
        r = requests.get("https://opensky-network.org/api/states/all", timeout=10)
        flights_raw = r.json().get('states', []) if r.status_code==200 else []
        flights = []
        for f in flights_raw:
            if f[5] is None or f[6] is None: continue
            flights.append({'icao24':f[0],'callsign':f[1],'longitude':f[5],'latitude':f[6],
                            'altitude': f[13] if f[13] else (f[7] if f[7] else 10000),
                            'velocity': f[9],'true_track': f[10]})
        return flights
    except:
        return []

def fetch_satellite_tle_data():
    global space_track_session
    if not space_track_session:
        login_space_track(SPACE_TRACK_USERNAME, SPACE_TRACK_PASSWORD)
        if not space_track_session: return []
    TLE_URL = "https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/limit/100/format/json"
    try:
        r = space_track_session.get(TLE_URL, timeout=15)
        tles = r.json() if r.status_code==200 else []
        return [t for t in tles if 'NORAD_CAT_ID' in t and 'TLE_LINE1' in t and 'TLE_LINE2' in t]
    except: return []

def get_satellite_position_from_tle(l1,l2,time_obj):
    try:
        jd = time_obj.timetuple().tm_yday + (time_obj.hour + time_obj.minute/60 + time_obj.second/3600)/24
        sat = Satrec.twoline2rv(l1,l2)
        e,r,v = sat.sgp4(time_obj.year,jd)
        if e==0:
            lon, lat, alt = WGS72.eci_to_geodetic(r, time_obj)
            return [math.degrees(lon), math.degrees(lat), alt*1000]
    except:
        pass
    return None

def process_satellites_and_routes(tles, route_dict):
    processed = []
    now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    current_ids = set()
    for tle in tles:
        norad = tle['NORAD_CAT_ID']
        current_ids.add(norad)
        pos = get_satellite_position_from_tle(tle['TLE_LINE1'], tle['TLE_LINE2'], now)
        if pos: processed.append({'norad_id': norad,'name':tle.get('OBJECT_NAME',f"SAT-{norad}"),'longitude':pos[0],'latitude':pos[1],'altitude':pos[2]})
    # eski uyduları temizle
    for k in list(route_dict.keys()):
        if k not in current_ids: del route_dict[k]
    return processed

def process_and_track_routes(entity_list, entity_id_key, route_dict, pos_func):
    ids_now = set()
    processed = []
    for e in entity_list:
        eid = e.get(entity_id_key)
        if not eid: continue
        ids_now.add(eid)
        pos = pos_func(e)
        if not pos: continue
        processed.append(e)
        if eid not in route_dict: route_dict[eid]=[]
        route_dict[eid].append(pos)
        if len(route_dict[eid])>ROUTE_HISTORY_LIMIT: route_dict[eid].pop(0)
    # eski rotaları temizle
    for eid in list(route_dict.keys()):
        if eid not in ids_now: del route_dict[eid]
    return processed

# -------------------------------
# LIVE DATA LOOP
# -------------------------------
def live_data_loop():
    while True:
        global_data["weather"] = fetch_weather_data()
        global_data["flights"] = process_and_track_routes(fetch_opensky_data(),'icao24',global_data["flight_routes"], lambda f:[f['longitude'],f['latitude'],f['altitude']])
        global_data["ships"] = process_and_track_routes(fetch_ais_data(),'mmsi',global_data["ship_routes"], lambda s:[s['longitude'],s['latitude'],0])
        global_data["satellites"] = process_satellites_and_routes(fetch_satellite_tle_data(), global_data["satellite_routes"])
        global_data["last_update"] = datetime.datetime.utcnow().isoformat()
        time.sleep(15)

# -------------------------------
# FLASK + SOCKET.IO
# -------------------------------
app = Flask(__name__)
socketio = SocketIO(app,cors_allowed_origins="*")

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>IAS4 Global Command Center</title>
<script src="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Cesium.js"></script>
<link href="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
</head>
<body>
<h1>IAS4 Global Command Center</h1>
<div id="cesiumContainer" style="width:100%; height:600px;"></div>
<script>
var viewer = new Cesium.Viewer('cesiumContainer', {
    terrainProvider: Cesium.createWorldTerrain(),
    imageryProvider: new Cesium.IonImageryProvider({ assetId: 2 }),
    baseLayerPicker: true
});

// Canlı uçak/gemi/uydu pozisyonları
function updateEntities(data){
    viewer.entities.removeAll();
    data.flights.forEach(f=>{
        viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(f.longitude,f.latitude,f.altitude),
            point:{pixelSize:5,color:Cesium.Color.RED},
            label:{text:f.callsign||f.icao24,font:'14pt sans-serif',verticalOrigin:Cesium.VerticalOrigin.BOTTOM}
        });
    });
    data.ships.forEach(s=>{
        viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,0),
            point:{pixelSize:5,color:Cesium.Color.BLUE},
            label:{text:s.name,font:'12pt sans-serif',verticalOrigin:Cesium.VerticalOrigin.BOTTOM}
        });
    });
    data.satellites.forEach(s=>{
        viewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,s.altitude),
            point:{pixelSize:3,color:Cesium.Color.GREEN},
            label:{text:s.name,font:'10pt sans-serif',verticalOrigin:Cesium.VerticalOrigin.BOTTOM}
        });
    });
}

function fetchAndUpdate(){
    fetch('/api/global_data').then(r=>r.json()).then(updateEntities);
}
setInterval(fetchAndUpdate,10000);
fetchAndUpdate();
</script>
</body>
</html>
"""

@app.route("/")
def index(): return render_template_string(INDEX_HTML)
@app.route("/api/global_data")
def api_data(): return jsonify(global_data)

# -------------------------------
# MAIN
# -------------------------------
if __name__=="__main__":
    Thread(target=live_data_loop, daemon=True).start()
    log_event("Flask + SocketIO başlatılıyor...")
    socketio.run(app, host="0.0.0.0", port=8080, allow_unsafe_werkzeug=True)