from flask import Flask, request, jsonify, render_template, send_file
import time, os, requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# -------- антиспам ----------
RATE = {}
def limit(ip):
    RATE.setdefault(ip, [])
    RATE[ip] = RATE[ip][-20:]
    RATE[ip].append(time.time())
    return len(RATE[ip]) < 20

# -------- расчёты ----------
def theory(area, d, t, price):
    cov = 1000 / (d * t)
    cons = area / cov * 1.15
    cost = cons * price
    return cons, cov, cost

def practice(area, cons, price):
    cov = area / cons
    cost = cons * price
    return cons, cov, cost

# -------- routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calc", methods=["POST"])
def calc():
    if not limit(request.remote_addr):
        return jsonify({"error": "Лимит"}), 429

    d = request.json
    res = []

    for p in d["paints"]:
        if d["mode"] == "theory":
            c, cov, cost = theory(d["area"], p["density"], p["thickness"], p["price"])
        else:
            c, cov, cost = practice(d["area"], p["consumption"], p["price"])

        res.append({
            "name": p["name"],
            "cost": round(cost, 2),
            "coverage": round(cov, 2),
            "consumption": round(c, 3),
            "sqm": round(cost / d["area"], 2)
        })

    cheap = min(res, key=lambda x: x["cost"])
    exp = max(res, key=lambda x: x["cost"])
    diff = round((exp["cost"] - cheap["cost"]) / exp["cost"] * 100, 2)

    return jsonify({
        "results": res,
        "cheaper": cheap,
        "economy": diff,
        "mode": d["mode"],
        "area": d["area"]
    })

@app.route("/api/pdf", methods=["POST"])
def pdf():
    d = request.json
    path = "/tmp/report.pdf"

    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"
    content = []

    content.append(Paragraph("<b>СРАВНЕНИЕ ДВУХ КРАСОК</b>", styles["Normal"]))
    content.append(Paragraph(f"Площадь: {d['area']} м²", styles["Normal"]))

    for p in d["results"]:
        content.append(Paragraph(
            f"{p['name']} — {p['cost']} ₽ ({p['sqm']} ₽/м²)",
            styles["Normal"]
        ))

    content.append(Paragraph(
        f"<b>Выгоднее:</b> {d['cheaper']['name']}<br/>"
        f"<b>Экономия:</b> {d['economy']}%",
        styles["Normal"]
    ))

    doc.build(content)
    return send_file(path, as_attachment=True)

@app.route("/api/order", methods=["POST"])
def order():
    d = request.json
    if TELEGRAM_TOKEN and ADMIN_CHAT_ID:
        text = (
            "🛒 ЗАКАЗ ИЗ WEBAPP\n\n"
            f"Тип расчёта: {d['mode']}\n"
            f"Площадь: {d['area']} м²\n"
            f"Краска: {d['paint']}\n"
            f"Экономия: {d['economy']}%\n\n"
            f"Поверхность: {d['surface']}\n"
            f"Цвет: {d['color']}\n"
            f"Количество: {d['qty']} кг"
        )
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_CHAT_ID, "text": text}
        )
    return jsonify({"ok": True})
