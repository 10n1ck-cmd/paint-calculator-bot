from flask import Flask, request, jsonify, render_template, send_file
import os, time, requests
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

# === CONFIG ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# === PDF FONT ===
pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

# === антиспам ===
RATE = {}
def limit(ip):
    RATE.setdefault(ip, [])
    RATE[ip] = RATE[ip][-15:]
    RATE[ip].append(time.time())
    return len(RATE[ip]) <= 15

# === calculations ===
def theory(area, d, t, price):
    coverage = 1000 / (d * t)
    cons = area / coverage * 1.15
    cost = cons * price
    return cons, coverage, cost

def practice(area, cons, price):
    coverage = area / cons
    cost = cons * price
    return cons, coverage, cost

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calc", methods=["POST"])
def calc():
    if not limit(request.remote_addr):
        return jsonify({"error": "limit"}), 429

    d = request.json
    results = []

    for p in d["paints"]:
        if d["mode"] == "theory":
            c, cov, cost = theory(
                d["area"], p["density"], p["thickness"], p["price"]
            )
        else:
            c, cov, cost = practice(
                d["area"], p["consumption"], p["price"]
            )

        results.append({
            "name": p["name"],
            "cost": round(cost, 2),
            "consumption": round(c, 3),
            "cost_per_sqm": round(cost / d["area"], 2)
        })

    cheaper = min(results, key=lambda x: x["cost"])
    expensive = max(results, key=lambda x: x["cost"])
    economy = round(
        (expensive["cost"] - cheaper["cost"]) / expensive["cost"] * 100, 2
    )

    return jsonify({
        "area": d["area"],
        "mode": d["mode"],
        "results": results,
        "cheaper": cheaper,
        "economy": economy
    })

# === PDF ===
@app.route("/api/pdf", methods=["POST"])
def pdf():
    d = request.json
    path = "/tmp/result.pdf"

    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"

    s = []
    s.append(Paragraph("<b>СРАВНЕНИЕ ДВУХ КРАСОК</b><br/><br/>", styles["Normal"]))
    s.append(Paragraph(f"Площадь: {d['area']} м²<br/><br/>", styles["Normal"]))

    for p in d["results"]:
        s.append(Paragraph(
            f"{p['name']} — {p['cost']} руб ({p['cost_per_sqm']} руб/м²)",
            styles["Normal"]
        ))

    s.append(Paragraph("<br/>", styles["Normal"]))
    s.append(Paragraph(
        f"<b>Выгоднее:</b> {d['cheaper']['name']}<br/>"
        f"<b>Экономия:</b> {d['economy']} %",
        styles["Normal"]
    ))

    doc.build(s)
    return send_file(path, as_attachment=True, download_name="comparison.pdf")

# === ORDER → ADMIN ONLY ===
@app.route("/api/order", methods=["POST"])
def o
