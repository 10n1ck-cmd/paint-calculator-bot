from flask import Flask, request, jsonify, render_template, send_file
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import os

app = Flask(__name__)

# === ШРИФТ С КИРИЛЛИЦЕЙ ===
FONT_PATH = "fonts/DejaVuSans.ttf"
pdfmetrics.registerFont(TTFont("DejaVu", FONT_PATH))

# === КАЛЬКУЛЯТОР ===
class PaintCalculator:

    @staticmethod
    def theoretical(p, area):
        coverage = 1000 / (p['density'] * p['thickness'])
        practical = (area / coverage) * 1.15
        cost = practical * p['price']
        return {
            "consumption": round(practical, 3),
            "coverage": round(coverage, 2),
            "cost": round(cost, 2),
            "cost_per_sqm": round(cost / area, 2)
        }

    @staticmethod
    def practical(p, area):
        cost = p['consumption'] * p['price']
        coverage = area / p['consumption']
        return {
            "consumption": round(p['consumption'], 3),
            "coverage": round(coverage, 2),
            "cost": round(cost, 2),
            "cost_per_sqm": round(cost / area, 2)
        }

    @staticmethod
    def compare(p1, p2, area, mode):
        r1 = PaintCalculator.theoretical(p1, area) if mode == "theoretical" else PaintCalculator.practical(p1, area)
        r2 = PaintCalculator.theoretical(p2, area) if mode == "theoretical" else PaintCalculator.practical(p2, area)

        cheaper = "paint1" if r1["cost"] < r2["cost"] else "paint2"

        return {
            "mode": mode,
            "area": area,
            "paint1": {**p1, **r1},
            "paint2": {**p2, **r2},
            "cheaper": cheaper
        }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/calculate", methods=["POST"])
def calculate():
    d = request.json
    res = PaintCalculator.compare(
        d["paint1"], d["paint2"],
        d["area"], d["mode"]
    )
    return jsonify(res)

@app.route("/api/pdf", methods=["POST"])
def pdf():
    r = request.json
    buf = BytesIO()

    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "DejaVu"
    styles["Title"].fontName = "DejaVu"

    doc = SimpleDocTemplate(buf, pagesize=A4)
    elements = []

    elements.append(Paragraph("Отчет расчета порошковой краски", styles["Title"]))
    elements.append(Paragraph(f"Тип расчета: {r['mode']}", styles["Normal"]))
    elements.append(Paragraph(f"Площадь: {r['area']} м²", styles["Normal"]))

    table_data = [
        ["Краска", "Расход кг", "Покрытие м²/кг", "Стоимость ₽", "Цена м² ₽"],
        [
            r["paint1"]["name"],
            r["paint1"]["consumption"],
            r["paint1"]["coverage"],
            r["paint1"]["cost"],
            r["paint1"]["cost_per_sqm"]
        ],
        [
            r["paint2"]["name"],
            r["paint2"]["consumption"],
            r["paint2"]["coverage"],
            r["paint2"]["cost"],
            r["paint2"]["cost_per_sqm"]
        ]
    ]

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.grey),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONT", (0,0), (-1,-1), "DejaVu")
    ]))

    elements.append(table)
    elements.append(Paragraph(f"Выгодная краска: {r['cheaper']}", styles["Normal"]))

    doc.build(elements)
    buf.seek(0)

    return send_file(buf, as_attachment=True, download_name="calculation.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run()
