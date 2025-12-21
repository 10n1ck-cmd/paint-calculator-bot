from flask import Flask, request, jsonify, render_template, send_file
import os
import requests
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

# ================= CALC =================
def theory(area, density, thickness, price):
    coverage = 1000 / (density * thickness)
    consumption = area / coverage * 1.15
    cost = consumption * price
    return round(consumption,3), round(cost,2), round(cost/area,2)

def practice(area, consumption, price):
    cost = consumption * price
    return round(consumption,3), round(cost,2), round(cost/area,2)

# ================= ROUTES =================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calc", methods=["POST"])
def calc():
    d = request.json
    res = []

    for p in d["paints"]:
        if d["mode"] == "theory":
            c, cost, sqm = theory(d["area"], p["density"], p["thickness"], p["price"])
        else:
            c, cost, sqm = practice(d["area"], p["consumption"], p["price"])

        res.append({
            "name": p["name"],
            "consumption": c,
            "cost": cost,
            "sqm": sqm
        })

    cheaper = min(res, key=lambda x: x["cost"])
    expensive = max(res, key=lambda x: x["cost"])
    economy = round((expensive["cost"] - cheaper["cost"]) / expensive["cost"] * 100, 2)

    return jsonify({
        "results": res,
        "cheaper": cheaper,
        "economy": economy
    })

@app.route("/api/pdf", methods=["POST"])
def pdf():
    d = request.json
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    s = getSampleStyleSheet()
    s["Normal"].fontName = "DejaVu"

    content = [
        Paragraph("<b>СРАВНЕНИЕ ДВУХ КРАСОК</b><br/><br/>", s["Normal"])
    ]

    for p in d["results"]:
        content.append(
            Paragraph(
                f"{p['name']} — {p['cost']} ₽ ({p['sqm']} ₽/м²)",
                s["Normal"]
            )
        )

    content.append(Paragraph("<br/>", s["Normal"]))
    content.append(
        Paragraph(
            f"<b>Выгоднее:</b> {d['cheaper']['name']}<br/>"
            f"<b>Экономия:</b> {d['economy']} %",
            s["Normal"]
        )
    )

    doc.build(content)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="comparison.pdf")

@app.route("/api/order", methods=["POST"])
def order():
    d = request.json
    tg = d.get("tg")

    text = (
        "💼 ЗАЯВКА ИЗ КАЛЬКУЛЯТОРА\n\n"
        f"👤 {tg.get('first_name')} @{tg.get('username')}\n"
        f"🆔 {tg.get('id')}\n\n"
        f"📐 Площадь: {d['area']} м²\n"
        f"📊 Режим: {d['mode']}\n\n"
    )

    for p in d["results"]:
        text += (
            f"🎨 {p['name']}\n"
            f"Расход: {p['consumption']} кг\n"
            f"Стоимость: {p['cost']} ₽\n"
            f"Цена за м²: {p['sqm']} ₽\n\n"
        )

    text += (
        f"🥇 Выгоднее: {d['cheaper']['name']}\n"
        f"📉 Экономия: {d['economy']} %\n\n"
        f"🧱 Поверхность: {d['surface']}\n"
        f"🎨 Цвет: {d['color']}\n"
        f"⚖️ Кол-во: {d['qty']} кг"
    )

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": ADMIN_CHAT_ID, "text": text}
    )

    return jsonify({"ok": True})
