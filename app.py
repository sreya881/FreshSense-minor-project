
from flask import Flask, request, jsonify, send_from_directory, Response
from datetime import datetime
from collections import deque
import joblib

app = Flask(__name__, static_folder=".")

# Load trained Random Forest model
model = joblib.load("freshsense_model.pkl")

# Sensor calibration assumptions
VC = 5.0
RL = 1000.0
DIVIDER_RESISTANCE = 25000.0

# Effective load resistance:
# Internal RL in parallel with external 10k + 15k divider
RL_EFFECTIVE = (RL * DIVIDER_RESISTANCE) / (RL + DIVIDER_RESISTANCE)

# Provisional no-fruit baseline
BASELINE_ADC = 77.5

# Convert baseline ADC into approximate GPIO voltage
BASELINE_GPIO_V = (BASELINE_ADC / 4095.0) * 3.3

# Recover original MQ135 AO voltage
BASELINE_AO_V = BASELINE_GPIO_V * (25.0 / 15.0)

# Calculate provisional R0
R0 = RL_EFFECTIVE * ((VC / BASELINE_AO_V) - 1)

# Approximate research training range
RESEARCH_MIN = 0.8818
RESEARCH_MAX = 0.9899

history = deque(maxlen=60)

latest_data = {
    "gas_value": None,
    "prediction": None,
    "last_update": None
}


def calculate_rs_r0(voltage_mv):

    gpio_voltage = voltage_mv / 1000.0

    # Recover MQ135 AO voltage from external divider
    ao_voltage = gpio_voltage * (25.0 / 15.0)

    if ao_voltage <= 0 or ao_voltage >= VC:
        raise ValueError("Invalid sensor voltage")

    # Calculate sensor resistance
    rs = RL_EFFECTIVE * ((VC / ao_voltage) - 1)

    # Calculate resistance ratio
    rs_r0 = rs / R0

    return rs_r0


def predict_freshness(rs_r0):

    prediction = model.predict([[rs_r0]])[0]

    raw_probabilities = model.predict_proba([[rs_r0]])[0]

    probabilities = {
        str(cls): float(prob)
        for cls, prob in zip(model.classes_, raw_probabilities)
    }

    confidence = max(probabilities.values())

    return str(prediction), confidence, probabilities


@app.route("/")
def dashboard():
    return send_from_directory(".", "freshsense_frontend.html")


@app.route("/sensor", methods=["POST"])
def receive_sensor_data():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "No JSON data received"}), 400

    try:
        gas_value = float(data["gas_value"])
        voltage_mv = float(data["voltage_mv"])
    except (KeyError, TypeError, ValueError):
        return jsonify({
            "error": "Valid gas_value and voltage_mv are required"
        }), 400

    try:
        rs_r0 = calculate_rs_r0(voltage_mv)

        label, confidence, probs = predict_freshness(rs_r0)

    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    now = datetime.now().timestamp()

    previous_values = [r["v"] for r in history]
    previous_values.append(gas_value)

    average = sum(previous_values) / len(previous_values)

    in_training_range = RESEARCH_MIN <= rs_r0 <= RESEARCH_MAX

    reading = {
        "t": now,
        "v": gas_value,
        "avg": average,
        "label": label,
        "conf": confidence,
        "probs": probs,
        "voltage_mv": voltage_mv,
        "rs_r0": round(rs_r0, 5),
        "calibration_warning": not in_training_range
    }

    history.append(reading)

    latest_data["gas_value"] = gas_value
    latest_data["prediction"] = label
    latest_data["last_update"] = now
    latest_data["confidence"] = confidence
    latest_data["probabilities"] = probs
    latest_data["rs_r0"] = round(rs_r0, 5)

    app.logger.info("ADC: %.2f", gas_value)
    app.logger.info("Rs/R0: %.5f", rs_r0)
    app.logger.info("ML prediction: %s", label)
    app.logger.info("ML confidence: %.2f%%", confidence * 100)

    return jsonify({
        "status": "success",
        "gas_value": gas_value,
        "prediction": label,
        "confidence": round(confidence * 100, 2),
        "probabilities": probs,
        "rs_r0": round(rs_r0, 5),
        "calibration_warning": not in_training_range
    })


@app.route("/api/state", methods=["GET"])
def api_state():

    now = datetime.now().timestamp()

    if history:
        latest = history[-1]
        connected = (now - latest["t"]) <= 6
    else:
        latest = None
        connected = False

    return jsonify({
        "source": "serial",
        "connected": connected,
        "port": "ESP32U",
        "baud": 115200,
        "server_time": now,
        "last_update": latest["t"] if latest else None,
        "latest": latest,
        "history": list(history),
        "total": len(history),
        "window": min(10, len(history)) if history else 10,

        "bands": [],

        "model": {
            "short": "Random Forest",
            "detail": "MQ135 research dataset model",
            "kind": "random_forest"
        },

        "baseline": BASELINE_ADC,
        "r0": round(R0, 2),
        "message": "Experimental calibration: verify RL and clean-air R0."
    })


@app.route("/data", methods=["GET"])
def get_data():
    return jsonify(latest_data)


@app.route("/api/export.csv", methods=["GET"])
def export_csv():

    lines = [
        "time,gas_value,average,prediction,confidence,voltage_mv,rs_r0"
    ]

    for r in history:

        time_string = datetime.fromtimestamp(
            r["t"]
        ).strftime("%Y-%m-%d %H:%M:%S")

        lines.append(
            f"{time_string},{r['v']},{r['avg']},"
            f"{r['label']},{r['conf']},"
            f"{r['voltage_mv']},{r['rs_r0']}"
        )

    return Response(
        "\n".join(lines),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=freshsense_readings.csv"
        }
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
