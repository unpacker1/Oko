#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import psutil
import socket
import subprocess
import platform
from flask import Flask, request, redirect, session, jsonify, render_template_string
from datetime import datetime

app = Flask(__name__)
app.secret_key = "termux-pro-secret"

# Login bilgileri
USER = "q"
PASS = "q"

# =========================
# Yardımcı Fonksiyonlar
# =========================

def run(cmd):
    try:
        return subprocess.check_output(cmd,shell=True,text=True,stderr=subprocess.STDOUT)
    except Exception as e:
        return f"Hata: {str(e)}"

def sysinfo():
    data={}
    try:
        data["CPU"] = psutil.cpu_percent(interval=1)
    except:
        data["CPU"] = "Erişim yok"
    try:
        data["RAM"] = psutil.virtual_memory().percent
    except:
        data["RAM"] = "Erişim yok"
    try:
        data["Disk"] = psutil.disk_usage("/").percent
    except:
        data["Disk"] = "Erişim yok"
    try:
        data["IP"] = socket.gethostbyname(socket.gethostname())
    except:
        data["IP"] = "Bilinmiyor"
    try:
        data["System"] = platform.system() + " " + platform.release()
    except:
        data["System"] = "Bilinmiyor"
    try:
        b = psutil.sensors_battery()
        if b:
            data["Battery"] = f"{b.percent}% {'Şarjda' if b.power_plugged else 'Şarjda değil'}"
        else:
            data["Battery"] = "Yok"
    except:
        data["Battery"] = "Bilinmiyor"
    return data

# =========================
# Login Sayfası
# =========================

@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u = request.form.get("user")
        p = request.form.get("pass")
        if u==USER and p==PASS:
            session["login"]=True
            return redirect("/panel")
    return """
<html>
<body style="background:#0f172a;color:white;font-family:Arial;text-align:center;padding-top:80px">
<h1>🔐 Termux PRO Panel</h1>
<form method=post>
<input name=user placeholder=Kullanıcı Adı style="padding:10px"><br><br>
<input name=pass type=password placeholder=Şifre style="padding:10px"><br><br>
<button style="padding:10px 30px">Login</button>
</form>
</body>
</html>
"""

# =========================
# Panel Sayfası
# =========================

@app.route("/panel")
def panel():
    if not session.get("login"):
        return redirect("/")
    # Hazır sorgular
    queries = [
        {"name":"Sistem Süresi","cmd":"uptime"},
        {"name":"RAM Kullanımı","cmd":"free -h"},
        {"name":"Disk Kullanımı","cmd":"df -h"},
        {"name":"CPU Durumu","cmd":"top -n 1 -b | head -n 10"},
        {"name":"Network","cmd":"ifconfig"},
        {"name":"Ping Google","cmd":"ping -c 3 google.com"},
        {"name":"Telefon Modeli","cmd":"getprop ro.product.model"},
        {"name":"Android Sürümü","cmd":"getprop ro.build.version.release"},
        {"name":"Kurulu Paketler","cmd":"pkg list-installed"}
    ]
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset=UTF-8>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>PRO Termux Panel</title>
<style>
body{{background:#020617;color:white;font-family:Arial;margin:0;padding:20px}}
h1{{text-align:center}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;text-align:center;font-size:16px}}
button{{padding:10px 15px;margin-top:10px;width:90%}}
pre{{background:#0f172a;padding:10px;border-radius:5px;max-height:300px;overflow:auto}}
</style>
</head>
<body>
<h1>🚀 Termux PRO Panel</h1>

<div class="grid">
<div class="card">
<h3>CPU</h3><div id="cpu"></div>
</div>
<div class="card">
<h3>RAM</h3><div id="ram"></div>
</div>
<div class="card">
<h3>Disk</h3><div id="disk"></div>
</div>
<div class="card">
<h3>IP</h3><div id="ip"></div>
</div>
<div class="card">
<h3>Battery</h3><div id="battery"></div>
</div>
<div class="card">
<h3>System</h3><div id="system"></div>
</div>
</div>

<h2>⚡ Hazır Sorgular</h2>
<div class="grid">
{"".join([f'<div class="card"><button onclick="run_query(`{q["cmd"]}`)">{q["name"]}</button></div>' for q in queries])}
</div>

<h2>🖥 Terminal</h2>
<input id=cmd placeholder="Komut yaz"><button onclick=run_cmd()>Çalıştır</button>
<pre id=out></pre>

<script>
function update(){
fetch('/api')
.then(r=>r.json())
.then(d=>{
document.getElementById('cpu').innerText=d.CPU+'%'
document.getElementById('ram').innerText=d.RAM+'%'
document.getElementById('disk').innerText=d.Disk+'%'
document.getElementById('ip').innerText=d.IP
document.getElementById('system').innerText=d.System
document.getElementById('battery').innerText=d.Battery
})
}
setInterval(update,2000)
update()

function run_query(cmd){
fetch("/cmd",{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{cmd:cmd}})})
.then(r=>r.text()).then(t=>document.getElementById('out').innerText=t)
}

function run_cmd(){
c=document.getElementById("cmd").value
fetch("/cmd",{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{cmd:c}})})
.then(r=>r.text()).then(t=>document.getElementById('out').innerText=t)
}
</script>

</body>
</html>
"""
    return html

# =========================
# API ve Terminal
# =========================

@app.route("/api")
def api():
    if not session.get("login"):
        return {}
    return jsonify(sysinfo())

@app.route("/cmd",methods=["POST"])
def cmd():
    if not session.get("login"):
        return ""
    c = request.json.get("cmd")
    return run(c)

# =========================
# Çalıştır
# =========================

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)