#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import psutil
import socket
import platform
import subprocess
from datetime import datetime
from flask import Flask, render_template_string

app = Flask(__name__)

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "Bilinmiyor"

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd,shell=True,text=True).strip()
    except:
        return "N/A"

def collect():

    data = {}

    data["Cihaz"] = {
        "Sistem": platform.system(),
        "Node": platform.node(),
        "Release": platform.release(),
        "Makine": platform.machine(),
        "IP": get_ip()
    }

    data["CPU"] = {
        "Kullanım %": psutil.cpu_percent(interval=1),
        "Çekirdek": psutil.cpu_count()
    }

    ram = psutil.virtual_memory()
    data["RAM"] = {
        "Toplam": f"{ram.total//(1024**3)} GB",
        "Kullanılan": f"{ram.used//(1024**3)} GB",
        "Yüzde": ram.percent
    }

    disk = psutil.disk_usage("/")
    data["Depolama"] = {
        "Toplam": f"{disk.total//(1024**3)} GB",
        "Kullanılan": f"{disk.used//(1024**3)} GB",
        "Yüzde": disk.percent
    }

    battery = psutil.sensors_battery()
    if battery:
        data["Batarya"] = {
            "Seviye": f"%{battery.percent}",
            "Şarj": battery.power_plugged
        }

    wifi = run_cmd("termux-wifi-connectioninfo")
    data["WiFi"] = wifi

    return data


HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="20">
<title>Ultra Termux Panel</title>

<style>

body{
background:#0f172a;
font-family:Arial;
color:white;
margin:0;
padding:20px;
}

h1{
text-align:center;
margin-bottom:30px;
}

.grid{
display:grid;
grid-template-columns:repeat(auto-fit,minmax(280px,1fr));
gap:20px;
}

.card{
background:#1e293b;
border-radius:10px;
padding:15px;
box-shadow:0 0 10px rgba(0,0,0,0.4);
}

.card h2{
margin-top:0;
font-size:18px;
border-bottom:1px solid #334155;
padding-bottom:5px;
}

pre{
white-space:pre-wrap;
font-size:13px;
}

.footer{
text-align:center;
margin-top:30px;
opacity:.7;
}

</style>
</head>

<body>

<h1>🚀 Ultra Termux Sistem Paneli</h1>

<div class="grid">

{% for k,v in data.items() %}

<div class="card">

<h2>{{k}}</h2>

<pre>{{v}}</pre>

</div>

{% endfor %}

</div>

<div class="footer">

Son güncelleme: {{time}}

</div>

</body>
</html>
"""

@app.route("/")
def index():

    data = collect()
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    return render_template_string(HTML,data=data,time=now)

if __name__ == "__main__":

    app.run(host="0.0.0.0",port=5000)