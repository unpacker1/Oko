# ias4_global_full.py
import requests, datetime, logging, time, math
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO
from threading import Thread
from sgp4.api import Satrec, WGS72

# -------------------------------
# CONFIG – Global Ayarlar
# -------------------------------
OPENWEATHER_API_KEY = "YOUR_OPENWEATHER_API_KEY"
SPACE_TRACK_USERNAME = "YOUR_SPACE_TRACK_USERNAME"
SPACE_TRACK_PASSWORD = "YOUR_SPACE_TRACK_PASSWORD"
AIS_HUB_API_KEY = "YOUR_AIS_HUB_API_KEY"

WEATHER_LOCATIONS = [
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
    {"name": "London", "lat": 51.5074, "lon": -0.1278},
    {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"name": "Sydney", "lat": -33.8688, "lon": 151.2093},
    {"name": "Cape Town", "lat": -33.9249, "lon": 18.4241},
    {"name": "Dubai", "lat": 25.276987, "lon": 55.296249},
    {"name": "Sao Paulo", "lat": -23.5505, "lon": -46.6333}
]

AIS_BOUNDING_BOX = "-90,-180,90,180"  # Dünya çapında

ROUTE_HISTORY_LIMIT = 30
SATELLITE_ROUTE_FORECAST_MINUTES = 60

# -------------------------------
# LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
def log_event(msg): logging.info(msg)

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
# SPACE TRACK LOGIN
# -------------------------------
def login_space_track(username, password):
    global space_track_session
    if not username or not password or username=="YOUR_SPACE_TRACK_USERNAME":
        log_event("Space-Track.org login atlandı (kullanıcı adı/şifre yok).")
        return None
    session = requests.Session()
    try:
        r = session.post("https://www.space-track.org/ajaxauth/login",
                         data={'identity':username,'password':password}, timeout=10)
        if r.status_code==200:
            space_track_session=session
            log_event("Space-Track.org login başarılı.")
            return session
    except: pass
    return None

# -------------------------------
# DATA COLLECTION
# -------------------------------
def fetch_weather_data():
    reports=[]
    if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY=="YOUR_OPENWEATHER_API_KEY":
        log_event("OpenWeatherMap API anahtarı yok.")
        return reports
    for loc in WEATHER_LOCATIONS:
        try:
            r=requests.get("http://api.openweathermap.org/data/2.5/weather",
                           params={"lat":loc["lat"],"lon":loc["lon"],
                                   "appid":OPENWEATHER_API_KEY,"units":"metric"},timeout=5)
            if r.status_code==200:
                d=r.json()
                reports.append({"name":loc["name"],"lat":loc["lat"],"lon":loc["lon"],
                                "temp":d["main"]["temp"],"desc":d["weather"][0]["description"]})
        except: continue
    return reports

def fetch_ais_data():
    ships=[]
    if not AIS_HUB_API_KEY or AIS_HUB_API_KEY=="YOUR_AIS_HUB_API_KEY":
        log_event("AIS Hub API anahtarı yok.")
        return ships
    min_lat,min_lon,max_lat,max_lon=map(float,AIS_BOUNDING_BOX.split(','))
    box=f"{min_lon},{min_lat},{max_lon},{max_lat}"
    try:
        r=requests.get("http://data.aishub.net/ws.php",params={"apikey":AIS_HUB_API_KEY,"box":box,"output":"json"},timeout=15)
        data=r.json()
        raw_list=data if isinstance(data,list) else data.get("ships",[])
        for s in raw_list:
            try:
                lat=float(s.get("LAT",0)); lon=float(s.get("LON",0))
                if lat==0 or lon==0: continue
                ships.append({"mmsi":s.get("MMSI"),"name":s.get("NAME",f"Gemi-{s.get('MMSI')}"),
                              "lon":lon,"lat":lat,"speed":float(s.get("SOG",0))})
            except: continue
    except: pass
    return ships

def fetch_opensky_data():
    flights=[]
    try:
        r=requests.get("https://opensky-network.org/api/states/all",timeout=10)
        states=r.json().get("states",[])
        for f in states:
            lon=f[5]; lat=f[6]; alt=f[13] if f[13] else (f[7] if f[7] else 10000)
            if lon is None or lat is None: continue
            flights.append({"icao24":f[0],"callsign":f[1].strip() if f[1] else "",
                            "lon":lon,"lat":lat,"alt":alt,"vel":f[9]})
    except: pass
    return flights

def fetch_satellite_tle_data():
    global space_track_session
    if not space_track_session:
        login_space_track(SPACE_TRACK_USERNAME, SPACE_TRACK_PASSWORD)
        if not space_track_session: return []
    url="https://www.space-track.org/basicspacedata/query/class/tle_latest/ORDINAL/1/EPOCH/%3Enow-30/orderby/NORAD_CAT_ID/limit/50/format/json"
    try:
        r=space_track_session.get(url,timeout=15)
        tles=r.json() if isinstance(r.json(),list) else []
        return [{"norad_id":t["NORAD_CAT_ID"],"name":t.get("OBJECT_NAME",f"SAT-{t['NORAD_CAT_ID']}"),
                 "line1":t["TLE_LINE1"],"line2":t["TLE_LINE2"]} for t in tles if "TLE_LINE1" in t]
    except: return []

# -------------------------------
# HELPER FUNCTIONS
# -------------------------------
def process_routes(entity_list,key,route_dict,extract_pos):
    current_ids=set(); processed=[]
    for e in entity_list:
        eid=e.get(key); 
        if not eid: continue
        current_ids.add(eid)
        pos=extract_pos(e); 
        if pos is None: continue
        processed.append(e)
        if eid not in route_dict: route_dict[eid]=[]
        route_dict[eid].append(pos)
        if len(route_dict[eid])>ROUTE_HISTORY_LIMIT: route_dict[eid].pop(0)
    for eid in list(route_dict.keys()):
        if eid not in current_ids: del route_dict[eid]
    return processed

def get_sat_pos(tle1,tle2,time_obj):
    try:
        jd=time_obj.timetuple().tm_yday + (time_obj.hour+time_obj.minute/60+time_obj.second/3600)/24
        sat=Satrec.twoline2rv(tle1,tle2)
        e,r,v=sat.sgp4(time_obj.year,jd)
        if e==0:
            return [r[0],r[1],r[2]*1000]  # x,y,z metre
    except: pass
    return None

def process_satellites(tles,route_dict):
    processed=[]; current_ids=set(); now=datetime.datetime.utcnow()
    for t in tles:
        nid=t["norad_id"]; current_ids.add(nid)
        pos=get_sat_pos(t["line1"],t["line2"],now)
        if pos: processed.append({"norad_id":nid,"name":t["name"],"lon":pos[0],"lat":pos[1],"alt":pos[2]})
    for nid in list(route_dict.keys()):
        if nid not in current_ids: del route_dict[nid]
    return processed

# -------------------------------
# LIVE DATA LOOP
# -------------------------------
def live_loop():
    while True:
        global_data["weather"]=fetch_weather_data()
        global_data["flights"]=process_routes(fetch_opensky_data(),"icao24",global_data["flight_routes"],
                                               lambda f:[f["lon"],f["lat"],f["alt"]])
        global_data["ships"]=process_routes(fetch_ais_data(),"mmsi",global_data["ship_routes"],
                                            lambda s:[s["lon"],s["lat"],0])
        global_data["satellites"]=process_satellites(fetch_satellite_tle_data(),global_data["satellite_routes"])
        global_data["last_update"]=datetime.datetime.utcnow().isoformat()
        time.sleep(15)

# -------------------------------
# FLASK + SOCKET.IO
# -------------------------------
app=Flask(__name__)
socketio=SocketIO(app,cors_allowed_origins="*")

index_html="""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<title>IAS4 Global</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.socket.io/4.6.1/socket.io.min.js"></script>
<style>html,body,#map{height:100%;margin:0;padding:0;}</style>
</head>
<body>
<div id="map"></div>
<script>
var map=L.map('map').setView([0,0],2);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19}).addTo(map);

var flightLayer=L.layerGroup().addTo(map);
var shipLayer=L.layerGroup().addTo(map);
var satLayer=L.layerGroup().addTo(map);

var socket=io();
socket.on('live_data',function(data){
    flightLayer.clearLayers();
    shipLayer.clearLayers();
    satLayer.clearLayers();

    (data.flights||[]).forEach(function(f){
        L.circleMarker([f.lat,f.lon],{radius:4,color:'red'}).bindPopup(f.callsign||f.icao24).addTo(flightLayer);
    });
    (data.ships||[]).forEach(function(s){
        L.circleMarker([s.lat,s.lon],{radius:4,color:'blue'}).bindPopup(s.name).addTo(shipLayer);
    });
    (data.satellites||[]).forEach(function(sat){
        L.circleMarker([sat.lat,s.lon],{radius:3,color:'green'}).bindPopup(sat.name).addTo(satLayer);
    });
});
</script>
</body>
</html>
"""

@app.route("/")
def index(): return render_template_string(index_html)
@app.route("/api/global_data")
def api_global(): return jsonify(global_data)

# -------------------------------
# MAIN
# -------------------------------
if __name__=="__main__":
    Thread(target=live_loop,daemon=True).start()
    socketio.run(app,host="0.0.0.0",port=3080,allow_unsafe_werkzeug=True)
