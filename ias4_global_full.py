# ias4_global_full.py
import requests
import datetime
import time
import logging
import random
import os
from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
from threading import Thread

# -------------------------------
# LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

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
    "last_update": None
}

# -------------------------------
# CONFIG
# -------------------------------
OPENWEATHER_API_KEY = ""  # İstersen ekle, demo modunda boş bırakılabilir
AIS_HUB_API_KEY = ""      # İstersen ekle, demo modunda boş bırakılabilir

WEATHER_LOCATIONS = [
    {"name": "Istanbul", "lat": 41.0082, "lon": 28.9784},
    {"name": "London", "lat": 51.5074, "lon": -0.1278},
    {"name": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    {"name": "New York", "lat": 40.7128, "lon": -74.0060},
]

# Demo AIS Box (tüm dünya)
AIS_BOUNDING_BOX = "-180,-90,180,90"

# -------------------------------
# DATA FETCH FUNCTIONS
# -------------------------------
def fetch_opensky_demo():
    """OpenSky anonim API ile uçakları çek (dünya genelinde demo)"""
    try:
        r = requests.get("https://opensky-network.org/api/states/all", timeout=10)
        if r.status_code == 200:
            states = r.json().get("states", [])
            flights = []
            for f in states:
                if f[5] is None or f[6] is None:
                    continue
                flights.append({
                    "icao24": f[0],
                    "callsign": f[1].strip() if f[1] else "",
                    "lon": f[5],
                    "lat": f[6],
                    "altitude": f[13] if f[13] else (f[7] if f[7] else 10000),
                    "velocity": f[9] if f[9] else 0
                })
            return flights
    except:
        return []
    return []

def fetch_ais_demo():
    """Demo gemi verisi. AIS Hub API key yoksa sabit veri gösterir."""
    if not AIS_HUB_API_KEY:
        # Demo verisi
        return [
            {"mmsi": "123456789", "name": "Demo Ship 1", "lon": -0.1278, "lat": 51.5074, "speed": 15},
            {"mmsi": "987654321", "name": "Demo Ship 2", "lon": 2.3522, "lat": 48.8566, "speed": 12}
        ]
    # API key varsa canlı çek
    try:
        min_lat, min_lon, max_lat, max_lon = map(float, AIS_BOUNDING_BOX.split(','))
        params = {"apikey": AIS_HUB_API_KEY, "box": f"{min_lon},{min_lat},{max_lon},{max_lat}", "output": "json"}
        r = requests.get("http://data.aishub.net/ws.php", params=params, timeout=10)
        if r.status_code == 200:
            ships_raw = r.json()
            ships = []
            if isinstance(ships_raw, list):
                for s in ships_raw:
                    try:
                        lon = float(s.get("LON", 0))
                        lat = float(s.get("LAT", 0))
                        if lon == 0 or lat == 0:
                            continue
                        ships.append({
                            "mmsi": s.get("MMSI"),
                            "name": s.get("NAME", f"Ship-{s.get('MMSI')}"),
                            "lon": lon,
                            "lat": lat,
                            "speed": float(s.get("SOG", 0))
                        })
                    except:
                        continue
            return ships
    except:
        pass
    return []

def fetch_weather_demo():
    """Demo hava durumu. OpenWeatherMap key yoksa sabit veri gösterir."""
    if not OPENWEATHER_API_KEY:
        return [{"name": loc["name"], "lat": loc["lat"], "lon": loc["lon"], "temp": 20, "desc": "Clear"} for loc in WEATHER_LOCATIONS]
    # Key varsa canlı çek
    weather = []
    for loc in WEATHER_LOCATIONS:
        try:
            params = {"lat": loc["lat"], "lon": loc["lon"], "appid": OPENWEATHER_API_KEY, "units": "metric"}
            r = requests.get("http://api.openweathermap.org/data/2.5/weather", params=params, timeout=5)
            if r.status_code == 200:
                data = r.json()
                weather.append({
                    "name": loc["name"],
                    "lat": loc["lat"],
                    "lon": loc["lon"],
                    "temp": data['main']['temp'],
                    "desc": data['weather'][0]['description']
                })
        except:
            continue
    return weather

# -------------------------------
# LIVE DATA LOOP
# -------------------------------
def live_data_loop():
    while True:
        try:
            global_data["flights"] = fetch_opensky_demo()
            global_data["ships"] = fetch_ais_demo()
            global_data["weather"] = fetch_weather_demo()
            global_data["last_update"] = datetime.datetime.utcnow().isoformat()
            socketio.emit("live_data", global_data)
        except Exception as e:
            log_event(f"Live loop error: {e}", logging.ERROR)
        time.sleep(10)

# -------------------------------
# FLASK + SOCKETIO
# -------------------------------
app = Flask(__name__)
app.template_folder = os.path.dirname(os.path.abspath(__file__))
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/")
def index():
    # CesiumJS 3D harita + uçak ve gemi pozisyonları
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>IAS4 Global Demo</title>
        <script src="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Cesium.js"></script>
    </head>
    <body>
        <h2>IAS4 Global Demo (Uçaklar & Gemiler & Hava Durumu)</h2>
        <div id="cesiumContainer" style="width:100%; height:600px;"></div>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
        <script>
            var viewer = new Cesium.Viewer('cesiumContainer', {terrainProvider: Cesium.createWorldTerrain()});
            var socket = io();

            socket.on('live_data', function(data){
                viewer.entities.removeAll();
                // Uçaklar
                data.flights.forEach(function(f){
                    viewer.entities.add({
                        position: Cesium.Cartesian3.fromDegrees(f.lon, f.lat, f.altitude || 10000),
                        point: {pixelSize: 10, color: Cesium.Color.RED},
                        label: {text: f.callsign || f.icao24, font:'14pt sans-serif', fillColor: Cesium.Color.WHITE}
                    });
                });
                // Gemiler
                data.ships.forEach(function(s){
                    viewer.entities.add({
                        position: Cesium.Cartesian3.fromDegrees(s.lon, s.lat, 0),
                        point: {pixelSize: 8, color: Cesium.Color.BLUE},
                        label: {text: s.name, font:'12pt sans-serif', fillColor: Cesium.Color.WHITE}
                    });
                });
            });
        </script>
    </body>
    </html>
    """

@app.route("/api/global_data")
def api_data():
    return jsonify(global_data)

# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    # Rastgele port seç
    port = random.randint(8000, 8999)
    log_event(f"Flask SocketIO demo başlatılıyor, port: {port}")

    # Canlı veri çekme thread'i
    Thread(target=live_data_loop, daemon=True).start()

    # Flask SocketIO çalıştır
    socketio.run(app, host="0.0.0.0", port=port)