#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import psutil
import socket
import subprocess
import platform
from flask import Flask, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = "termux-secret"


USER="admin"
PASS="termux123"


def run(cmd):
    try:
        return subprocess.check_output(cmd,shell=True,text=True).strip()
    except:
        return "N/A"


def sysinfo():

    data={}

    try:
        cpu=psutil.cpu_percent(interval=1)
    except:
        cpu="N/A"

    try:
        ram=psutil.virtual_memory().percent
    except:
        ram="N/A"

    try:
        disk=psutil.disk_usage("/").percent
    except:
        disk="N/A"

    data["cpu"]=cpu
    data["ram"]=ram
    data["disk"]=disk
    data["ip"]=socket.gethostbyname(socket.gethostname())
    data["system"]=platform.system()+" "+platform.release()

    return data


@app.route("/",methods=["GET","POST"])
def login():

    if request.method=="POST":

        u=request.form.get("user")
        p=request.form.get("pass")

        if u==USER and p==PASS:

            session["login"]=True
            return redirect("/panel")

    return """
    <html>
    <body style="background:#0f172a;color:white;font-family:Arial;text-align:center;padding-top:100px">

    <h1>🔐 Termux PRO Panel</h1>

    <form method=post>

    <input name=user placeholder=User style="padding:10px"><br><br>

    <input name=pass type=password placeholder=Password style="padding:10px"><br><br>

    <button style="padding:10px 30px">Login</button>

    </form>

    </body>
    </html>
    """


@app.route("/panel")
def panel():

    if not session.get("login"):
        return redirect("/")

    return """
<html>
<head>

<meta name=viewport content="width=device-width, initial-scale=1">

<style>

body{
background:#020617;
color:white;
font-family:Arial;
margin:0;
padding:20px;
}

.grid{
display:grid;
grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
gap:20px;
}

.card{
background:#1e293b;
padding:20px;
border-radius:10px;
text-align:center;
font-size:20px;
}

button{
padding:10px 20px;
margin-top:20px;
}

input{
padding:10px;
width:70%;
}

</style>

</head>

<body>

<h1>🚀 Termux PRO Panel</h1>

<div class=grid>

<div class=card id=cpu>CPU</div>
<div class=card id=ram>RAM</div>
<div class=card id=disk>DISK</div>
<div class=card id=ip>IP</div>

</div>

<br><br>

<h2>🖥 Terminal</h2>

<input id=cmd placeholder="komut yaz">

<button onclick=run()>Çalıştır</button>

<pre id=out></pre>

<script>

function update(){

fetch('/api')

.then(r=>r.json())

.then(d=>{

cpu.innerHTML="CPU "+d.cpu+"%"
ram.innerHTML="RAM "+d.ram+"%"
disk.innerHTML="DISK "+d.disk+"%"
ip.innerHTML="IP "+d.ip

})

}

setInterval(update,2000)

update()

function run(){

c=document.getElementById("cmd").value

fetch("/cmd",{

method:"POST",

headers:{"Content-Type":"application/json"},

body:JSON.stringify({cmd:c})

})

.then(r=>r.text())

.then(t=>{

out.innerText=t

})

}

</script>

</body>

</html>
"""


@app.route("/api")
def api():

    if not session.get("login"):
        return {}

    return jsonify(sysinfo())


@app.route("/cmd",methods=["POST"])
def cmd():

    if not session.get("login"):
        return ""

    c=request.json.get("cmd")

    return run(c)


app.run(host="0.0.0.0",port=5000)