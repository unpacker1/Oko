#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import psutil
import socket
import platform
import subprocess
import json
from datetime import datetime
from flask import Flask, render_template_string

app = Flask(__name__)


def run_cmd(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True, text=True)
        return out.strip()
    except:
        return "N/A"


def run_json(cmd):
    try:
        out = subprocess.check_output(cmd, shell=True, text=True)
        return json.loads(out)
    except:
        return "N/A"


def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "Bilinmiyor"


def get_cpu():
    try:
        return {
            "Kullanım %": psutil.cpu_percent(interval=1),
            "Çekirdek": psutil.cpu_count()
        }
    except:
        return {"Durum":"CPU bilgisi alınamadı"}


def get_ram():
    try:
        ram = psutil.virtual_memory()
        return {
            "Toplam": f"{ram.total//(1024**3)} GB",
            "Kullanılan": f"{ram.used//(1024**3)} GB",
            "Yüzde": ram.percent
        }
    except:
        return {"Durum":"RAM bilgisi alınamadı"}


def get_disk():
    try:
        disk = psutil.disk_usage("/")
        return {
            "Toplam": f"{disk.total//(1024**3)} GB",
            "Kullanılan": f"{disk.used//(1024**3)} GB",
            "Yüzde": disk.percent
        }
    except:
        return {"Durum":"Disk bilgisi alınamadı"}


def get_battery():
    try:
        b = psutil.sensors_battery()
        if b:
            return {
                "Seviye": f"%{b.percent}",
                "Şarj": b.power_plugged
            }
    except:
        pass
    return {"Durum":"Batarya bilgisi yok"}


def collect():

    data = {}

    data["Cihaz"] = {
        "Sistem": platform.system(),
        "Release": platform.release(),
        "Makine": platform.machine(),
        "IP": get_ip()
    }

    data["CPU"] = get_cpu()
    data["RAM"] = get_ram()
    data["Depolama"] = get_disk()
    data["Batarya"] = get_battery()

    wifi = run_json("termux-wifi-connectioninfo")

    data["WiFi"] = wifi

    data["Network"] = {
        "Hostname": socket.gethostname()
    }

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
border-radius:12px;
padding:16px;
box-shadow:0 0 12px rgba(0,0,0,0.5);
}

.card h2{
margin:0 0 10px 0;
font-size:18px;
border-bottom:1px solid #334155;
padding-bottom:6px;
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