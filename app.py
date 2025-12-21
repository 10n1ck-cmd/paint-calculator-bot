from flask import Flask, request, jsonify, render_template, send_file
import time, os, requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

# --- PDF FONT ---
pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# --- антиспам ---
RATE = {}
def limit(ip):
    RATE.setdefault(ip, [])
    RATE[ip] = RATE[ip][-20:]
    RATE[ip].append(time.time())
    return len(RATE[ip]) <= 20

# --- расчёты ---
def theory(area, d, t, price):
    coverage = 1000 / (d * t)
    consumption = area / coverage * 1.15
    cost = consumption * price
    return consumption, coverage, cost

def practice(area, consumption, price):
    coverage = area / consumption
    cost = consumption * price
    return consumption, coverage, cost

# --- routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calc", methods=["POST"])
def calc():
    if not limit(request.remote_addr):
        return jsonify({"error": "Лимит запросов"}), 429

    d = request.json
    results = []

    for p in d["paints"]:
        if d["mode"] == "theory":
            cons, cov, cost = theory(
                d["area"], p["density"], p["thickness"], p["price"]
            )
        else:
            cons, cov, cost = practice(
                d["area"], p["consumption"], p["price"]
            )

        results.append({
            "name": p["name"],
            "cost": round(cost, 2),
            "coverage": round(cov, 2),
            "consumption": round(cons, 3),
            "cost_per_sqm": round(cost / d["area"], 2)
        })

    cheaper = min(results, key=lambda x: x["cost"])
    expensive = max(results, key=lambda x: x["cost"])
    economy = round(
        (expensive["cost"] - cheaper["cost"]) / expensive["cost"] * 100, 2
    )

    return jsonify({
        "mode": d["mode"],
        "area": d["area"],
        "results": results,
        "cheaper": cheaper,
        "economy": economy
    })

# --- PDF ---
@app.route("/api/pdf", methods=["POST"])
def pdf():
    d = request.json
    path = "/tmp/report.pdf"

    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"

    story = []
    story.append(Paragraph("<b>СРАВНЕНИЕ ДВУХ КРАСОК</b>", styles["Normal"]))
    story.append(Paragraph(f"Площадь: {d['area']} м²", styles["Normal"]))
    story.append(Paragraph("<br/>", styles["Normal"]))

    for p in d["results"]:
        story.append(Paragraph(
            f"{p['name']}: {p['cost']} руб. "
            f"({p['cost_per_sqm']} руб./м²)",
            styles["Normal"]
        ))

    story.append(Paragraph("<br/>", styles["Normal"]))
    story.append(Paragraph(
        f"<b>Выгоднее:</b> {d['cheaper']['name']}<br/>"
        f"<b>Экономия:</b> {d['economy']} %",
        styles["Normal"]
    ))

    doc.build(story)
    return send_file(path, as_attachment=True, download_name="comparison.pdf")

# --- заказ админу ---
@app.route("/api/order", methods=["POST"])
def order():
    d = request.json

    if TELEGRAM_TOKEN and ADMIN_CHAT_ID:
        text = (
            "💼 ЗАПРОС НА ВЫГОДНОЕ ПРЕДЛОЖЕНИЕ\n\n"
            f"Тип расчёта: {d['mode']}\n"
            f"Площадь: {d['area']} м²\n\n"
            f"Рекомендованная краска: {d['cheaper']['name']}\n"
            f"Экономия: {d['economy']} %\n\n"
            f"Тип поверхности: {d['surface']}\n"
            f"Цвет: {d['color']}\n"
            f"Количество: {d['qty']} кг\n"
        )

        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_CHAT_ID, "text": text}
        )

    return jsonify({"success": True})
