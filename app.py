from flask import Flask, request, jsonify, render_template, send_file
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

app = Flask(__name__)

# ===== КАЛЬКУЛЯТОР =====

class PaintCalculator:

    @staticmethod
    def theoretical(p, area):
        coverage = 1000 / (p['density'] * p['thickness'])
        theoretical = area / coverage
        practical = theoretical * 1.15
        cost = practical * p['price']
        return {
            "coverage_area": round(coverage, 2),
            "practical_consumption": round(practical, 3),
            "product_cost": round(cost, 2),
            "cost_per_sqm": round(cost / area, 2)
        }

    @staticmethod
    def practical(p, area):
        cost = p['real_consumption'] * p['price']
        coverage = area / p['real_consumption']
        return {
            "real_consumption": round(p['real_consumption'], 3),
            "coverage_area": round(coverage, 2),
            "product_cost": round(cost, 2),
            "cost_per_sqm": round(cost / area, 2)
        }

    @staticmethod
    def compare(p1, p2, area, mode):
        r1 = PaintCalculator.theoretical(p1, area) if mode == "theoretical" else PaintCalculator.practical(p1, area)
        r2 = PaintCalculator.theoretical(p2, area) if mode == "theoretical" else PaintCalculator.practical(p2, area)

        diff = r2["product_cost"] - r1["product_cost"]
        cheaper = "paint1" if diff > 0 else "paint2"

        return {
            "paint1": {**p1, **r1},
            "paint2": {**p2, **r2},
            "comparison": {
                "cheaper_paint": cheaper,
                "calculation_type": mode,
                "difference": abs(round(diff, 2))
            },
            "product_area": area
        }


# ===== ROUTES =====

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calculate", methods=["POST"])
def calculate():
    d = request.json
    result = PaintCalculator.compare(
        d["paint1"], d["paint2"],
        d["product_area"], d["calc_type"]
    )
    return jsonify(success=True, result=result)


@app.route("/api/pdf", methods=["POST"])
def pdf():
    r = request.json
    buf = BytesIO()

    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elems = []

    elems.append(Paragraph("Отчет расчета порошковой краски", styles["Title"]))
    elems.append(Paragraph(f"Площадь изделия: {r['product_area']} м²", styles["Normal"]))
    elems.append(Paragraph(f"Тип расчета: {r['comparison']['calculation_type']}", styles["Normal"]))

    table_data = [
        ["Краска", "Расход кг", "Покрытие м²/кг", "Стоимость ₽", "Цена м² ₽"]
    ]

    for k in ["paint1", "paint2"]:
        p = r[k]
        table_data.append([
            p["name"],
            p.get("practical_consumption", p.get("real_consumption")),
            p["coverage_area"],
            p["product_cost"],
            p["cost_per_sqm"]
        ])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.grey),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
    ]))

    elems.append(table)
    elems.append(Paragraph(
        f"Выгодная краска: {r['comparison']['cheaper_paint']}",
        styles["Heading2"]
    ))

    doc.build(elems)
    buf.seek(0)

    return send_file(buf, as_attachment=True, download_name="calculation.pdf", mimetype="application/pdf")


if __name__ == "__main__":
    app.run()
