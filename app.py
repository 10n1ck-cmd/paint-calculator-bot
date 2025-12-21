from flask import Flask, request, jsonify, render_template, send_file
import os
import time
import requests

from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)

# ================== CONFIG ==================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")

# ================== PDF FONT ==================
pdfmetrics.registerFont(
    TTFont("DejaVu", "fonts/DejaVuSans.ttf")
)

# ================== ANTISPAM ==================
RATE = {}

def limit(ip):
    RATE.setdefault(ip, [])
    RATE[ip] = RATE[ip][-15:]
    RATE[ip].append(time.time())
    return len(RATE[ip]) <= 15

# ================== CALCULATIONS ==================
def theory(area, density, thickness, price):
    coverage = 1000 / (density * thickness)
    consumption = area / coverage * 1.15
    cost = consumption * price
    return consumption, coverage, cost

def practice(area, consumption, price):
    coverage = area / consumption
    cost = consumption * price
    return consumption, coverage, cost

# ================== ROUTES ==================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calc", methods=["POST"])
def calc():
    if not limit(request.remote_addr):
        return jsonify({"error": "rate limit"}), 429

    data = request.json
    results = []

    for p in data["paints"]:
        if data["mode"] == "theory":
            cons, cov, cost = theory(
                data["area"],
                p["density"],
                p["thickness"],
                p["price"]
            )
        else:
            cons, cov, cost = practice(
                data["area"],
                p["consumption"],
                p["price"]
            )

        results.append({
            "name": p["name"],
            "consumption": round(cons, 3),
            "cost": round(cost, 2),
            "cost_per_sqm": round(cost / data["area"], 2)
        })

    cheaper = min(results, key=lambda x: x["cost"])
    expensive = max(results, key=lambda x: x["cost"])

    economy = round(
        (expensive["cost"] - cheaper["cost"]) / expensive["cost"] * 100,
        2
    )

    return jsonify({
        "area": data["area"],
        "mode": data["mode"],
        "results": results,
        "cheaper": cheaper,
        "economy": economy
    })

# ================== PDF ==================
@app.route("/api/pdf", methods=["POST"])
def pdf():
    data = request.json
    path = "/tmp/comparison.pdf"

    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"

    content = []
    content.append(
        Paragraph("<b>СРАВНЕНИЕ ДВУХ КРАСОК</b><br/><br/>", styles["Normal"])
    )
    content.append(
        Paragraph(f"Площадь: {data['area']} м²<br/><br/>", styles["Normal"])
    )

    for p in data["results"]:
        content.append(
            Paragraph(
                f"{p['name']} — {p['cost']} руб "
                f"({p['cost_per_sqm']} руб/м²)",
                styles["Normal"]
            )
        )

    content.append(Paragraph("<br/>", styles["Normal"]))
    content.append(
        Paragraph(
            f"<b>Выгоднее:</b> {data['cheaper']['name']}<br/>"
            f"<b>Экономия:</b> {data['economy']} %",
            styles["Normal"]
        )
    )

    doc.build(content)
    return send_file(
        path,
        as_attachment=True,
        download_name="comparison.pdf"
    )

# ================== ORDER → ADMIN ==================
@app.route("/api/order", methods=["POST"])
def order():
    data = request.json
    tg = data.get("tg_user")

    text = (
        "💼 ЗАЯВКА ИЗ WEBAPP\n\n"
        f"👤 {tg['first_name'] if tg else 'Web'} "
        f"(@{tg['username'] if tg and tg.get('username') else '-'})\n"
        f"🆔 {tg['id'] if tg else '-'}\n\n"
        f"📐 Площадь: {data['area']} м²\n"
        f"🥇 Выгоднее: {data['cheaper']['name']}\n"
        f"📉 Экономия: {data['economy']} %\n\n"
        f"🧱 Поверхность: {data['surface']}\n"
        f"🎨 Цвет: {data['color']}\n"
        f"⚖️ Количество: {data['qty']} кг"
    )

    # ❗ ОТПРАВКА ТОЛЬКО АДМИНУ
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": ADMIN_CHAT_ID,
            "text": text
        }
    )

    return jsonify({"ok": True})

# ================== RUN ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
