# ias4_global_full.py
import datetime, math, time, random, logging
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO
from threading import Thread

# -------------------------------
# LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(msg):
    logging.info(msg)

# -------------------------------
# GLOBAL DATA STORE (DEMO)
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

# -------------------------------
# DEMO DATA GENERATORS
# -------------------------------
def generate_demo_flights():
    flights = []
    for i in range(5):
        lon = random.uniform(-180, 180)
        lat = random.uniform(-85, 85)
        alt = random.uniform(9000, 12000)  # metre
        flights.append({
            "icao24": f"DEMO{i}",
            "callsign": f"FLIGHT{i}",
            "longitude": lon,
            "latitude": lat,
            "altitude": alt,
            "velocity": random.uniform(200, 300)
        })
        # Rota kaydı
        if f"DEMO{i}" not in global_data["flight_routes"]:
            global_data["flight_routes"][f"DEMO{i}"] = []
        global_data["flight_routes"][f"DEMO{i}"].append([lon, lat, alt])
        if len(global_data["flight_routes"][f"DEMO{i}"]) > 30:
            global_data["flight_routes"][f"DEMO{i}"].pop(0)
    return flights

def generate_demo_ships():
    ships = []
    for i in range(5):
        lon = random.uniform(-180, 180)
        lat = random.uniform(-85, 85)
        ships.append({
            "mmsi": f"SHIP{i}",
            "name": f"SHIP{i}",
            "longitude": lon,
            "latitude": lat,
            "speed": random.uniform(10, 30)
        })
        if f"SHIP{i}" not in global_data["ship_routes"]:
            global_data["ship_routes"][f"SHIP{i}"] = []
        global_data["ship_routes"][f"SHIP{i}"].append([lon, lat, 0])
        if len(global_data["ship_routes"][f"SHIP{i}"]) > 30:
            global_data["ship_routes"][f"SHIP{i}"].pop(0)
    return ships

def generate_demo_satellites():
    sats = []
    for i in range(3):
        lon = random.uniform(-180, 180)
        lat = random.uniform(-85, 85)
        alt = random.uniform(400, 800) * 1000  # metre
        sats.append({
            "norad_id": f"SAT{i}",
            "name": f"SAT{i}",
            "longitude": lon,
            "latitude": lat,
            "altitude": alt
        })
        if f"SAT{i}" not in global_data["satellite_routes"]:
            global_data["satellite_routes"][f"SAT{i}"] = []
        global_data["satellite_routes"][f"SAT{i}"].append([lon, lat, alt])
        if len(global_data["satellite_routes"][f"SAT{i}"]) > 30:
            global_data["satellite_routes"][f"SAT{i}"].pop(0)
    return sats

def generate_demo_weather():
    locations = ["New York","London","Tokyo","Sydney","Cape Town","Dubai"]
    weather = []
    for loc in locations:
        weather.append({
            "name": loc,
            "latitude": random.uniform(-85, 85),
            "longitude": random.uniform(-180, 180),
            "temperature": random.uniform(-10, 35),
            "description": "Sunny"
        })
    return weather

# -------------------------------
# DEMO DATA LOOP
# -------------------------------
def demo_data_loop():
    while True:
        global_data["flights"] = generate_demo_flights()
        global_data["ships"] = generate_demo_ships()
        global_data["satellites"] = generate_demo_satellites()
        global_data["weather"] = generate_demo_weather()
        global_data["last_update"] = datetime.datetime.utcnow().isoformat()
        socketio.emit("live_data", global_data)
        time.sleep(5)  # 5 saniyede bir güncelle

# -------------------------------
# FLASK + SOCKET.IO
# -------------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>IAS4 Global Demo</title>
    <script src="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Cesium.js"></script>
    <link href="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
</head>
<body>
<h1>IAS4 Global Demo</h1>
<div id="cesiumContainer" style="width:100%; height:600px;"></div>
<script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
<script>
var viewer = new Cesium.Viewer('cesiumContainer', {
    terrainProvider: Cesium.createWorldTerrain(),
    shouldAnimate: true
});

var flightEntities = {};
var shipEntities = {};
var satEntities = {};

var socket = io();
socket.on('live_data', function(data){
    // Flights
    data.flights.forEach(function(f){
        if(!flightEntities[f.icao24]){
            flightEntities[f.icao24] = viewer.entities.add({
                position: Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, f.altitude),
                point: { pixelSize: 10, color: Cesium.Color.RED },
                label: { text: f.callsign, font: '14pt sans-serif', style: Cesium.LabelStyle.FILL, verticalOrigin: Cesium.VerticalOrigin.BOTTOM }
            });
        } else {
            flightEntities[f.icao24].position = Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, f.altitude);
        }
    });
    // Ships
    data.ships.forEach(function(s){
        if(!shipEntities[s.mmsi]){
            shipEntities[s.mmsi] = viewer.entities.add({
                position: Cesium.Cartesian3.fromDegrees(s.longitude, s.latitude, 0),
                point: { pixelSize: 8, color: Cesium.Color.BLUE },
                label: { text: s.name, font: '12pt sans-serif', style: Cesium.LabelStyle.FILL, verticalOrigin: Cesium.VerticalOrigin.BOTTOM }
            });
        } else {
            shipEntities[s.mmsi].position = Cesium.Cartesian3.fromDegrees(s.longitude, s.latitude, 0);
        }
    });
    // Satellites
    data.satellites.forEach(function(sat){
        if(!satEntities[sat.norad_id]){
            satEntities[sat.norad_id] = viewer.entities.add({
                position: Cesium.Cartesian3.fromDegrees(sat.longitude, sat.latitude, sat.altitude),
                point: { pixelSize: 6, color: Cesium.Color.YELLOW },
                label: { text: sat.name, font: '10pt sans-serif', style: Cesium.LabelStyle.FILL, verticalOrigin: Cesium.VerticalOrigin.BOTTOM }
            });
        } else {
            satEntities[sat.norad_id].position = Cesium.Cartesian3.fromDegrees(sat.longitude, sat.latitude, sat.altitude);
        }
    });
});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/global_data")
def api_global_data():
    return jsonify(global_data)

# -------------------------------
# RUN SERVER
# -------------------------------
if __name__ == "__main__":
    demo_thread = Thread(target=demo_data_loop, daemon=True)
    demo_thread.start()

    # Random port (8000-8999)
    port = random.randint(8000, 8999)
    log_event(f"Demo sunucu başlatılıyor: http://0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)