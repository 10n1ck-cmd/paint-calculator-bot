from flask import Flask, request, jsonify, render_template, send_file
import os, time, requests
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

# --- fonts ---
pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# --- антиспам ---
RATE = {}
def limit(ip):
    RATE.setdefault(ip, [])
    RATE[ip] = RATE[ip][-10:]
    RATE[ip].append(time.time())
    return len(RATE[ip]) <= 10

# --- расчёты ---
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
        "mode": d["mode"],
        "area": d["area"],
        "results": results,
        "cheaper": cheaper,
        "expensive": expensive,
        "economy": economy
    })

# --- PDF ---
def make_pdf(data):
    path = "/tmp/comparison.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"

    s = []
    s.append(Paragraph("<b>СРАВНЕНИЕ ДВУХ КРАСОК</b><br/><br/>", styles["Normal"]))
    s.append(Paragraph(f"Площадь: {data['area']} м²<br/><br/>", styles["Normal"]))

    for p in data["results"]:
        s.append(Paragraph(
            f"{p['name']}: {p['cost']} руб. "
            f"({p['cost_per_sqm']} руб./м²)",
            styles["Normal"]
        ))

    s.append(Paragraph("<br/>", styles["Normal"]))
    s.append(Paragraph(
        f"<b>Выгоднее:</b> {data['cheaper']['name']}<br/>"
        f"<b>Экономия:</b> {data['economy']} %",
        styles["Normal"]
    ))

    doc.build(s)
    return path

# --- заказ админу ---
@app.route("/api/order", methods=["POST"])
def order():
    d = request.json
    pdf_path = make_pdf(d)

    tg = d.get("tg_user")

    text = (
        "💼 ЗАПРОС НА ВЫГОДНОЕ ПРЕДЛОЖЕНИЕ\n\n"
        f"👤 {tg['first_name'] if tg else 'Web'} "
        f"(@{tg['username'] if tg and tg.get('username') else '-'})\n"
        f"🆔 {tg['id'] if tg else '-'}\n\n"
        f"📐 Площадь: {d['area']} м²\n\n"
        f"🥇 Выгоднее: {d['cheaper']['name']}\n"
        f"🥈 Вторая: {d['expensive']['name']}\n"
        f"📉 Экономия: {d['economy']} %\n\n"
        f"🧱 Поверхность: {d['surface']}\n"
        f"🎨 Цвет: {d['color']}\n"
        f"⚖️ Количество: {d['qty']} кг"
    )

    # сообщение админу
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": ADMIN_CHAT_ID, "text": text}
    )

    # PDF админу
    with open(pdf_path, "rb") as f:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument",
            data={"chat_id": ADMIN_CHAT_ID},
            files={"document": f}
        )

    return jsonify({"ok": True})
