from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

class Calculator:

    @staticmethod
    def theoretical(area, density, thickness, price):
        coverage = 1000 / (density * thickness)
        consumption = (area / coverage) * 1.15
        cost = consumption * price
        return consumption, coverage, cost

    @staticmethod
    def practical(area, consumption, price):
        coverage = area / consumption
        cost = consumption * price
        return consumption, coverage, cost


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/calculate", methods=["POST"])
def calculate():
    try:
        data = request.json
        mode = data["mode"]
        area = float(data["area"])

        if mode == "theoretical":
            p = data["paint1"]
            cons, cov, cost = Calculator.theoretical(
                area,
                float(p["density"]),
                float(p["thickness"]),
                float(p["price"])
            )

        elif mode == "practical":
            p = data["paint1"]
            cons, cov, cost = Calculator.practical(
                area,
                float(p["consumption"]),
                float(p["price"])
            )
        else:
            return jsonify({"error": "Unknown mode"}), 400

        return jsonify({
            "paint1": {
                "consumption": round(cons, 3),
                "coverage": round(cov, 2),
                "cost": round(cost, 2),
                "cost_per_sqm": round(cost / area, 2)
            }
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400
