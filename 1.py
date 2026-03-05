#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-

import subprocess
import json
from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

# Termux API komutlarını çalıştırıp JSON çıktısını döndüren yardımcı fonksiyon
def termux_command(cmd, timeout=5):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                # JSON değilse düz metin olarak döndür
                return {"çıktı": result.stdout.strip()}
        else:
            return {"hata": result.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"hata": "Komut zaman aşımına uğradı."}
    except Exception as e:
        return {"hata": str(e)}

# Tüm verileri toplayan ana fonksiyon
def collect_all_data():
    data = {}

    # Telefon bilgileri
    data['cihaz'] = termux_command("termux-telephony-deviceinfo")

    # Batarya durumu
    data['batarya'] = termux_command("termux-battery-status")

    # Konum (önce son bilinen konumu dene, olmazsa ağ tabanlı dene)
    data['konum'] = termux_command("termux-location -r last")
    if data['konum'].get("hata"):
        data['konum'] = termux_command("termux-location -p network")

    # Ağ bilgileri
    data['wifi'] = termux_command("termux-wifi-connectioninfo")
    data['cell'] = termux_command("termux-cellulario-info")

    # Sensörler (ilk 5 sensörü al)
    sensor_data = termux_command("termux-sensor -l")
    sensors_list = []
    if isinstance(sensor_data, list):
        sensors_list = sensor_data[:5]  # çok fazla sensör varsa ilk 5
    elif isinstance(sensor_data, dict) and "hata" not in sensor_data:
        sensors_list = list(sensor_data.keys())[:5]
    data['sensörler'] = {}
    for s in sensors_list:
        data['sensörler'][s] = termux_command(f"termux-sensor -s {s} -n 1")

    # Kamera bilgisi
    data['kamera'] = termux_command("termux-camera-info")

    # Rehber (ilk 5 kişi)
    contacts = termux_command("termux-contact-list")
    if isinstance(contacts, list):
        data['rehber'] = contacts[:5]
    else:
        data['rehber'] = contacts

    # SMS (son 5 SMS)
    sms = termux_command("termux-sms-inbox -l 5")
    if isinstance(sms, list):
        data['sms'] = sms
    else:
        data['sms'] = {"bilgi": "SMS alınamadı veya izin yok"}

    # Çağrı kayıtları (son 5)
    calls = termux_command("termux-call-log -l 5")
    if isinstance(calls, list):
        data['çağrılar'] = calls
    else:
        data['çağrılar'] = {"bilgi": "Çağrı kaydı alınamadı"}

    # Depolama bilgisi (termux-storage-get ile belirli dosyalar listelenebilir, burada basit bir kontrol)
    storage = termux_command("termux-storage-list")
    data['depolama'] = storage

    # Pano içeriği
    data['pano'] = termux_command("termux-clipboard-get")

    return data

# HTML şablonu (modern ve mobil uyumlu)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>📱 Termux Telefon Paneli</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="30"> <!-- 30 saniyede bir otomatik yenile -->
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
            background: #f0f2f5;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        h1 {
            text-align: center;
            color: #2c3e50;
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .card {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: transform 0.2s;
            display: flex;
            flex-direction: column;
        }
        .card:hover {
            transform: translateY(-4px);
        }
        .card-header {
            background: #3498db;
            color: white;
            padding: 12px 16px;
            font-size: 1.2rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .card-header i { font-size: 1.4rem; }
        .card-body {
            padding: 16px;
            overflow-x: auto;
            flex: 1;
        }
        pre {
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            padding: 12px;
            margin: 0;
            font-size: 0.85rem;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-height: 300px;
            overflow-y: auto;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            color: #7f8c8d;
            font-size: 0.9rem;
        }
        .error { color: #e74c3c; }
        .loading { opacity: 0.6; }
    </style>
</head>
<body>
    <h1>📊 Kapsamlı Telefon Bilgi Paneli</h1>
    <div class="grid">
        {% for baslik, veri in data.items() %}
        <div class="card">
            <div class="card-header">
                <span>{% if baslik == 'cihaz' %}📱{% elif baslik == 'batarya' %}🔋{% elif baslik == 'konum' %}📍{% elif baslik == 'wifi' %}📶{% elif baslik == 'cell' %}📡{% elif baslik == 'sensörler' %}📳{% elif baslik == 'kamera' %}📷{% elif baslik == 'rehber' %}👥{% elif baslik == 'sms' %}✉️{% elif baslik == 'çağrılar' %}📞{% elif baslik == 'depolama' %}💾{% elif baslik == 'pano' %}📋{% else %}📌{% endif %}</span>
                <span>{{ baslik.upper() }}</span>
            </div>
            <div class="card-body">
                {% if veri is mapping %}
                    {% if veri.get('hata') %}
                        <pre class="error">{{ veri.hata }}</pre>
                    {% else %}
                        <pre>{{ veri | tojson(indent=2, ensure_ascii=False) }}</pre>
                    {% endif %}
                {% elif veri is iterable and veri is not string %}
                    <pre>{{ veri | tojson(indent=2, ensure_ascii=False) }}</pre>
                {% else %}
                    <pre>{{ veri }}</pre>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
    <div class="footer">
        Son güncelleme: {{ zaman }} • Sayfa her 30 saniyede bir yenilenir.
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    from datetime import datetime
    veriler = collect_all_data()
    zaman = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    return render_template_string(HTML_TEMPLATE, data=veriler, zaman=zaman)

if __name__ == '__main__':
    # Flask'ı tüm arayüzlerde çalıştır (aynı ağdaki cihazlar erişebilir)
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)