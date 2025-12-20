from flask import Flask, request, jsonify, render_template, send_file
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

app = Flask(__name__)

pdfmetrics.registerFont(TTFont("DejaVu", "fonts/DejaVuSans.ttf"))

class Calc:

    @staticmethod
    def theory(p, area):
        coverage = 1000 / (p["density"] * p["thickness"])
        cons = (area / coverage) * 1.15
        cost = cons * p["price"]
        return cons, coverage, cost

    @staticmethod
    def practice(p, area):
        coverage = area / p["consumption"]
        cost = p["consumption"] * p["price"]
        return p["consumption"], coverage, cost

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calculate", methods=["POST"])
def calculate():
    d = request.json
    p = d["paint1"]
    area = d["area"]

    if d["mode"] == "theoretical":
        cons, cov, cost = Calc.theory(p, area)
    else:
        cons, cov, cost = Calc.practice(p, area)

    return jsonify({
        "paint1": {
            "name": p["name"],
            "consumption": round(cons, 3),
            "coverage": round(cov, 2),
            "cost": round(cost, 2),
            "cost_per_sqm": round(cost / area, 2)
        }
    })
