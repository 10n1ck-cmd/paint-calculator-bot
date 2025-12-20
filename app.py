from flask import Flask, request, jsonify, render_template
import time
import requests
import os

app = Flask(__name__)

# ---------------- АНТИСПАМ ----------------
RATE = {}
LIMIT = 15
WINDOW = 60

def check(ip):
    now = time.time()
    RATE.setdefault(ip, [])
    RATE[ip] = [t for t in RATE[ip] if now - t < WINDOW]
    if len(RATE[ip]) >= LIMIT:
        return False
    RATE[ip].append(now)
    return True

# ---------------- РАСЧЁТЫ ----------------
def theory(area, d, t, price):
    coverage = 1000 / (d * t)
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

@app.route("/api/calc", methods=["POST"])
def calc():
    if not check(request.remote_addr):
        return jsonify({"error": "Лимит запросов"}), 429

    d = request.json
    mode = d["mode"]
    area = float(d["area"])
    results = []

    for p in d["paints"]:
        if mode == "theory":
            cons, cov, cost = theory(
                area, p["density"], p["thickness"], p["price"]
            )
        else:
            cons, cov, cost = practice(
                area, p["consumption"], p["price"]
            )

        results.append({
            "name": p["name"],
            "cost": round(cost, 2),
            "consumption": round(cons, 3),
            "coverage": round(cov, 2),
            "cost_per_sqm": round(cost / area, 2)
        })

    cheaper = min(results, key=lambda x: x["cost"])
    expensive = max(results, key=lambda x: x["cost"])

    diff_percent = round(
        (expensive["cost"] - cheaper["cost"]) / expensive["cost"] * 100, 2
    )

    return jsonify({
        "mode": mode,
        "area": area,
        "results": results,
        "cheaper": cheaper,
        "diff_percent": diff_percent
    })

@app.route("/api/order", methods=["POST"])
def order():
    d = request.json
    token = os.environ.get("TELEGRAM_TOKEN")
    admin = os.environ.get("ADMIN_CHAT_ID")

    if token and admin:
        text = (
            "🛒 ЗАЯВКА ИЗ WEBAPP\n\n"
            f"Тип расчёта: {d['mode']}\n"
            f"Площадь: {d['area']} м²\n\n"
            f"Рекомендуемая краска: {d['paint']}\n"
            f"Экономия: {d['economy']}%\n\n"
            f"Тип поверхности: {d['surface']}\n"
            f"Цвет: {d['color']}\n"
            f"Количество: {d['qty']} кг\n\n"
            f"Расчётная стоимость: {d['cost']} ₽"
        )
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": admin, "text": text}
        )

    return jsonify({"success": True})
