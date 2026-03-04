# ias4_global_full.py
import random, time, math, datetime, logging
from threading import Thread
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO
import socket

# -------------------------------
# LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log(msg):
    logging.info(msg)

# -------------------------------
# GLOBAL DATA STORE
# -------------------------------
global_data = {
    "flights": [],
    "ships": [],
    "satellites": [],
    "flight_routes": {},
    "ship_routes": {},
    "satellite_routes": {},
    "last_update": None
}

# -------------------------------
# CONFIG
# -------------------------------
ROUTE_HISTORY_LIMIT = 30
SATELLITE_ROUTE_FORECAST_MINUTES = 60

# -------------------------------
# DEMO DATA GENERATOR
# -------------------------------
def generate_demo_flights(num=20):
    flights = []
    for i in range(num):
        icao24 = f"FL{i:04d}"
        lat = random.uniform(-60, 60)
        lon = random.uniform(-180, 180)
        alt = random.uniform(8000, 12000)
        vel = random.uniform(200, 300)
        heading = random.uniform(0, 360)
        flights.append({
            "icao24": icao24,
            "callsign": f"DEMO{i}",
            "longitude": lon,
            "latitude": lat,
            "altitude": alt,
            "velocity": vel,
            "true_track": heading
        })
    return flights

def generate_demo_ships(num=15):
    ships = []
    for i in range(num):
        mmsi = f"SH{i:04d}"
        lat = random.uniform(-60, 60)
        lon = random.uniform(-180, 180)
        cog = random.uniform(0, 360)
        sog = random.uniform(5, 30)
        ships.append({
            "mmsi": mmsi,
            "name": f"DEMO_SHIP{i}",
            "longitude": lon,
            "latitude": lat,
            "course": cog,
            "speed": sog
        })
    return ships

def generate_demo_satellites(num=5):
    sats = []
    for i in range(num):
        norad_id = f"SAT{i:03d}"
        lat = random.uniform(-60, 60)
        lon = random.uniform(-180, 180)
        alt = random.uniform(400, 800)
        sats.append({
            "norad_id": norad_id,
            "name": f"DEMO_SAT{i}",
            "latitude": lat,
            "longitude": lon,
            "altitude": alt*1000  # metre
        })
    return sats

# -------------------------------
# ROUTE UPDATES
# -------------------------------
def update_routes(entity_list, id_key, route_dict):
    current_ids = set()
    for ent in entity_list:
        ent_id = ent[id_key]
        current_ids.add(ent_id)
        pos = [ent['longitude'], ent['latitude'], ent.get('altitude', 0)]
        if ent_id not in route_dict:
            route_dict[ent_id] = []
        route_dict[ent_id].append(pos)
        if len(route_dict[ent_id]) > ROUTE_HISTORY_LIMIT:
            route_dict[ent_id].pop(0)
    # Remove missing
    to_remove = [eid for eid in route_dict if eid not in current_ids]
    for eid in to_remove:
        del route_dict[eid]
    return entity_list

# -------------------------------
# LIVE DATA LOOP
# -------------------------------
def live_data_loop():
    while True:
        # Uçak
        flights = generate_demo_flights()
        global_data['flights'] = update_routes(flights, 'icao24', global_data['flight_routes'])
        # Gemi
        ships = generate_demo_ships()
        global_data['ships'] = update_routes(ships, 'mmsi', global_data['ship_routes'])
        # Uydu
        sats = generate_demo_satellites()
        global_data['satellites'] = update_routes(sats, 'norad_id', global_data['satellite_routes'])
        global_data['last_update'] = datetime.datetime.utcnow().isoformat()
        socketio.emit('live_data', global_data)
        time.sleep(10)

# -------------------------------
# FLASK + SOCKETIO
# -------------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# -------------------------------
# INDEX HTML
# -------------------------------
index_html = """
<!DOCTYPE html>
<html>
<head>
<title>IAS4 Demo Global Command Center</title>
<script src="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Cesium.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.1/socket.io.min.js"></script>
<style>
html,body,#cesiumContainer{width:100%;height:100%;margin:0;padding:0;overflow:hidden;}
#controlPanel{position:absolute;top:10px;left:10px;background:rgba(255,255,255,0.8);padding:10px;z-index:10;}
</style>
</head>
<body>
<div id="cesiumContainer"></div>
<div id="controlPanel">
<input type="checkbox" id="flights_cb" checked> Uçaklar<br>
<input type="checkbox" id="ships_cb" checked> Gemiler<br>
<input type="checkbox" id="sats_cb" checked> Uydular
</div>
<script>
var viewer = new Cesium.Viewer('cesiumContainer', {terrainProvider: Cesium.createWorldTerrain()});
var flightEntities = {}, shipEntities = {}, satEntities = {};

var socket = io();

socket.on('live_data', function(data){
    // Uçaklar
    if(document.getElementById('flights_cb').checked){
        data.flights.forEach(f=>{
            if(!flightEntities[f.icao24]){
                flightEntities[f.icao24] = viewer.entities.add({
                    name: f.callsign,
                    position: Cesium.Cartesian3.fromDegrees(f.longitude,f.latitude,f.altitude),
                    point: {pixelSize:10,color:Cesium.Color.RED}
                });
            } else {
                flightEntities[f.icao24].position = Cesium.Cartesian3.fromDegrees(f.longitude,f.latitude,f.altitude);
            }
        });
    }
    // Gemiler
    if(document.getElementById('ships_cb').checked){
        data.ships.forEach(s=>{
            if(!shipEntities[s.mmsi]){
                shipEntities[s.mmsi] = viewer.entities.add({
                    name: s.name,
                    position: Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,0),
                    point: {pixelSize:10,color:Cesium.Color.BLUE}
                });
            } else {
                shipEntities[s.mmsi].position = Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,0);
            }
        });
    }
    // Uydular
    if(document.getElementById('sats_cb').checked){
        data.satellites.forEach(s=>{
            if(!satEntities[s.norad_id]){
                satEntities[s.norad_id] = viewer.entities.add({
                    name: s.name,
                    position: Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,s.altitude),
                    point: {pixelSize:10,color:Cesium.Color.GREEN}
                });
            } else {
                satEntities[s.norad_id].position = Cesium.Cartesian3.fromDegrees(s.longitude,s.latitude,s.altitude);
            }
        });
    }
});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(index_html)

@app.route("/api/global_data")
def api_data():
    return jsonify(global_data)

# -------------------------------
# RANDOM PORT HELPER
# -------------------------------
def get_random_port():
    return random.randint(8000, 8999)

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    data_thread = Thread(target=live_data_loop, daemon=True)
    data_thread.start()

    port = get_random_port()
    log(f"Server starting on http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port)