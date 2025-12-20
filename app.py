from flask import Flask, request, jsonify, render_template, send_file
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
import time
import os
import requests

app = Flask(__name__)

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))
styles = getSampleStyleSheet()
styles["Normal"].fontName = "DejaVu"

# ---------------- АНТИСПАМ ----------------
RATE_LIMIT = {}
LIMIT = 10      # запросов
WINDOW = 60     # секунд

def check_limit(ip):
    now = time.time()
    RATE_LIMIT.setdefault(ip, [])
    RATE_LIMIT[ip] = [t for t in RATE_LIMIT[ip] if now - t < WINDOW]
    if len(RATE_LIMIT[ip]) >= LIMIT:
        return False
    RATE_LIMIT[ip].append(now)
    return True

# ---------------- КАЛЬКУЛЯТОР ----------------
def theory(area, density, thickness, price):
    coverage = 1000 / (density * thickness)
    cons = (area / coverage) * 1.15
    cost = cons * price
    return cons, coverage, cost

def practice(area, cons, price):
    coverage = area / cons
    cost = cons * price
    return cons, coverage, cost

# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calculate", methods=["POST"])
def calculate():
    if not check_limit(request.remote_addr):
        return jsonify({"error": "Слишком много запросов"}), 429

    d = request.json
    area = float(d["area"])

    results = []
    for p in d["paints"]:
        if d["mode"] == "theoretical":
            cons, cov, cost = theory(
                area, p["density"], p["thickness"], p["price"]
            )
        else:
            cons, cov, cost = practice(
                area, p["consumption"], p["price"]
            )

        results.append({
            "name": p["name"],
            "consumption": round(cons, 3),
            "coverage": round(cov, 2),
            "cost": round(cost, 2),
            "cost_per_sqm": round(cost / area, 2)
        })

    cheaper = min(results, key=lambda x: x["cost"])

    return jsonify({
        "results": results,
        "cheaper": cheaper
    })

@app.route("/api/pdf", methods=["POST"])
def pdf():
    d = request.json
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    story = []

    story.append(Paragraph("Отчёт расчёта порошковой краски", styles["Title"]))
    story.append(Paragraph(f"Площадь: {d['area']} м²", styles["Normal"]))

    table = [["Краска", "Расход кг", "Стоимость ₽", "Цена м² ₽"]]
    for r in d["results"]:
        table.append([
            r["name"], r["consumption"], r["cost"], r["cost_per_sqm"]
        ])

    t = Table(table)
    t.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
    ]))
    story.append(t)

    doc.build(story)
    buf.seek(0)

    return send_file(buf, as_attachment=True, download_name="report.pdf")

@app.route("/api/order", methods=["POST"])
def order():
    d = request.json
    token = os.environ.get("TELEGRAM_TOKEN")
    admin = os.environ.get("ADMIN_CHAT_ID")

    if token and admin:
        text = (
            "🛒 ЗАКАЗ С WEBAPP\n\n"
            f"Имя: {d['name']}\n"
            f"Телефон: {d['phone']}\n"
            f"Комментарий: {d['comment']}\n\n"
            f"Краска: {d['paint']}\n"
            f"Стоимость: {d['cost']} ₽"
        )
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": admin, "text": text}
        )

    return jsonify({"success": True})
