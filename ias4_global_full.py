import random
import time
import math
import datetime
from threading import Thread
from flask import Flask, render_template_string
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------------------
# CONFIG
# ---------------------------
ENTITY_COUNT_FLIGHT = 25
ENTITY_COUNT_SHIP = 15
ENTITY_COUNT_SAT = 6
ROUTE_LENGTH = 40

# ---------------------------
# DATA STORE
# ---------------------------
data_store = {
    "flights": {},
    "ships": {},
    "sats": {}
}

# ---------------------------
# ENTITY INIT
# ---------------------------
def create_entities():
    for i in range(ENTITY_COUNT_FLIGHT):
        data_store["flights"][f"F{i}"] = {
            "lat": random.uniform(-60,60),
            "lon": random.uniform(-180,180),
            "alt": random.uniform(9000,12000),
            "speed": random.uniform(220,280),
            "heading": random.uniform(0,360),
            "route":[]
        }

    for i in range(ENTITY_COUNT_SHIP):
        data_store["ships"][f"S{i}"] = {
            "lat": random.uniform(-60,60),
            "lon": random.uniform(-180,180),
            "speed": random.uniform(10,25),
            "heading": random.uniform(0,360),
            "route":[]
        }

    for i in range(ENTITY_COUNT_SAT):
        data_store["sats"][f"T{i}"] = {
            "lat": random.uniform(-60,60),
            "lon": random.uniform(-180,180),
            "alt": random.uniform(400000,800000),
            "speed": 7.8,  # km/s approx
            "heading": random.uniform(0,360),
            "route":[]
        }

# ---------------------------
# REALISTIC MOVEMENT
# ---------------------------
def move_entity(e, is_sat=False):
    distance = e["speed"] * 0.00005
    rad = math.radians(e["heading"])
    e["lat"] += distance * math.cos(rad)
    e["lon"] += distance * math.sin(rad)

    if e["lat"] > 85 or e["lat"] < -85:
        e["heading"] += 180

    if e["lon"] > 180: e["lon"] -= 360
    if e["lon"] < -180: e["lon"] += 360

    e["route"].append([e["lon"], e["lat"], e.get("alt",0)])
    if len(e["route"]) > ROUTE_LENGTH:
        e["route"].pop(0)

# ---------------------------
# LIVE LOOP
# ---------------------------
def live_loop():
    while True:
        for f in data_store["flights"].values():
            move_entity(f)
        for s in data_store["ships"].values():
            move_entity(s)
        for t in data_store["sats"].values():
            move_entity(t, True)

        socketio.emit("update", data_store)
        time.sleep(1)

# ---------------------------
# CLEAN INDEX
# ---------------------------
INDEX = """
<!DOCTYPE html>
<html>
<head>
<title>IAS4 Global Command</title>
<script src="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Cesium.js"></script>
<link href="https://cesium.com/downloads/cesiumjs/releases/1.106/Build/Cesium/Widgets/widgets.css" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>

<style>
html,body,#map{margin:0;height:100%;width:100%;overflow:hidden;font-family:Arial;}
#panel{
position:absolute;
top:15px;
left:15px;
background:rgba(0,0,0,0.7);
color:white;
padding:15px;
border-radius:10px;
z-index:10;
}
label{display:block;margin-bottom:6px;}
</style>
</head>

<body>
<div id="panel">
<label><input type="checkbox" id="cb_f" checked> Uçak Trafiği</label>
<label><input type="checkbox" id="cb_s" checked> Gemi Trafiği</label>
<label><input type="checkbox" id="cb_t" checked> Uydu Trafiği</label>
</div>
<div id="map"></div>

<script>
var viewer = new Cesium.Viewer('map',{
    baseLayerPicker:false,
    timeline:false,
    animation:false,
    terrainProvider: Cesium.createWorldTerrain()
});

var socket = io();
var entities = {};

function clearLayer(prefix){
    for(var id in entities){
        if(id.startsWith(prefix)){
            viewer.entities.remove(entities[id]);
            delete entities[id];
        }
    }
}

socket.on("update", function(data){

    if(document.getElementById("cb_f").checked){
        for(var id in data.flights){
            var f = data.flights[id];
            if(!entities["F"+id]){
                entities["F"+id] = viewer.entities.add({
                    position: Cesium.Cartesian3.fromDegrees(f.lon,f.lat,f.alt),
                    point:{pixelSize:8,color:Cesium.Color.RED},
                    polyline:{
                        positions:f.route.map(r=>Cesium.Cartesian3.fromDegrees(r[0],r[1],r[2])),
                        width:2,
                        material:Cesium.Color.RED
                    }
                });
            }else{
                entities["F"+id].position = Cesium.Cartesian3.fromDegrees(f.lon,f.lat,f.alt);
            }
        }
    } else { clearLayer("F"); }

    if(document.getElementById("cb_s").checked){
        for(var id in data.ships){
            var s = data.ships[id];
            if(!entities["S"+id]){
                entities["S"+id] = viewer.entities.add({
                    position: Cesium.Cartesian3.fromDegrees(s.lon,s.lat,0),
                    point:{pixelSize:8,color:Cesium.Color.BLUE},
                    polyline:{
                        positions:s.route.map(r=>Cesium.Cartesian3.fromDegrees(r[0],r[1],0)),
                        width:2,
                        material:Cesium.Color.BLUE
                    }
                });
            }else{
                entities["S"+id].position = Cesium.Cartesian3.fromDegrees(s.lon,s.lat,0);
            }
        }
    } else { clearLayer("S"); }

    if(document.getElementById("cb_t").checked){
        for(var id in data.sats){
            var t = data.sats[id];
            if(!entities["T"+id]){
                entities["T"+id] = viewer.entities.add({
                    position: Cesium.Cartesian3.fromDegrees(t.lon,t.lat,t.alt),
                    point:{pixelSize:8,color:Cesium.Color.LIME},
                    polyline:{
                        positions:t.route.map(r=>Cesium.Cartesian3.fromDegrees(r[0],r[1],r[2])),
                        width:2,
                        material:Cesium.Color.LIME
                    }
                });
            }else{
                entities["T"+id].position = Cesium.Cartesian3.fromDegrees(t.lon,t.lat,t.alt);
            }
        }
    } else { clearLayer("T"); }

});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return INDEX

# ---------------------------
# START
# ---------------------------
if __name__ == "__main__":
    create_entities()
    Thread(target=live_loop, daemon=True).start()

    port = random.randint(8000, 9000)
    print(f"\n🚀 SERVER RUNNING:\nhttp://0.0.0.0:{port}\n")
    socketio.run(app, host="0.0.0.0", port=port)