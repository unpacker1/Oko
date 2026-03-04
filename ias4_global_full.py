# ias4_global_full.py
import random
import datetime
import time
import logging
from threading import Thread
from flask import Flask, render_template_string, jsonify
from flask_socketio import SocketIO

# -------------------------------
# LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# -------------------------------
# FLASK + SOCKET.IO SETUP
# -------------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# -------------------------------
# GLOBAL DATA STORE
# -------------------------------
global_data = {
    "flights": [],
    "ships": [],
    "last_update": None
}

# -------------------------------
# RANDOM DEMO DATA GENERATOR
# -------------------------------
def generate_demo_flights(num=50):
    flights = []
    for i in range(num):
        flights.append({
            "icao24": f"F{i:03}",
            "callsign": f"DEMO{i:03}",
            "longitude": random.uniform(-180, 180),
            "latitude": random.uniform(-90, 90),
            "altitude": random.uniform(9000, 12000),  # metre
            "velocity": random.uniform(200, 300),  # m/s
            "true_track": random.uniform(0, 360)
        })
    return flights

def generate_demo_ships(num=30):
    ships = []
    for i in range(num):
        ships.append({
            "mmsi": f"S{i:03}",
            "name": f"DEMO_SHIP_{i:03}",
            "longitude": random.uniform(-180, 180),
            "latitude": random.uniform(-90, 90),
            "speed": random.uniform(0, 20),
            "course": random.uniform(0, 360)
        })
    return ships

# -------------------------------
# LIVE DATA LOOP
# -------------------------------
def live_data_loop():
    while True:
        try:
            global_data["flights"] = generate_demo_flights()
            global_data["ships"] = generate_demo_ships()
            global_data["last_update"] = datetime.datetime.utcnow().isoformat()
            socketio.emit("live_data", global_data)
            logging.info(f"Updated demo data: {len(global_data['flights'])} flights, {len(global_data['ships'])} ships")
        except Exception as e:
            logging.error(f"Error generating demo data: {e}")
        time.sleep(5)  # 5 saniyede bir güncelle

# -------------------------------
# ROUTES
# -------------------------------
@app.route("/")
def index():
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>IAS4 Global Demo</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>html, body, #map {{ width:100%; height:100%; margin:0; padding:0; }}</style>
    <link href="https://unpkg.com/maplibre-gl@2.4.0/dist/maplibre-gl.css" rel="stylesheet" />
    <script src="https://unpkg.com/maplibre-gl@2.4.0/dist/maplibre-gl.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/deck.gl@8.10.20/dist.min.js"></script>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body>
<div id="map"></div>
<script>
const socket = io();

// MapLibre GL JS init
const map = new maplibregl.Map({{
    container: 'map',
    style: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    center: [0,0],
    zoom: 1
}});

// Deck.gl overlay
let flightsLayer = null;
let shipsLayer = null;

function updateLayers(data) {{
    const flightsData = data.flights.map(f => ({
        position: [f.longitude, f.latitude, f.altitude],
        icao24: f.icao24,
        callsign: f.callsign
    }));

    const shipsData = data.ships.map(s => ({
        position: [s.longitude, s.latitude, 0],
        name: s.name
    }));

    flightsLayer = new deck.ScatterplotLayer({{
        id: 'flights',
        data: flightsData,
        getPosition: d => d.position,
        getFillColor: [255, 0, 0],
        getRadius: 100000,
        radiusUnits: 'meters',
        pickable: true
    }});

    shipsLayer = new deck.ScatterplotLayer({{
        id: 'ships',
        data: shipsData,
        getPosition: d => d.position,
        getFillColor: [0, 0, 255],
        getRadius: 50000,
        radiusUnits: 'meters',
        pickable: true
    }});

    const deckgl = new deck.DeckGL({{
        map: map,
        layers: [flightsLayer, shipsLayer]
    }});
}}

socket.on('live_data', (data) => {{
    updateLayers(data);
}});
</script>
</body>
</html>
"""
    return render_template_string(html)

@app.route("/api/global_data")
def api_global_data():
    return jsonify(global_data)

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    # Live data loop thread
    t = Thread(target=live_data_loop, daemon=True)
    t.start()

    # Random port seçimi 8000-8999
    import random
    port = random.randint(8000, 8999)
    logging.info(f"Starting Flask Socket.IO server on port {port}")
    socketio.run(app, host="0.0.0.0", port=port)