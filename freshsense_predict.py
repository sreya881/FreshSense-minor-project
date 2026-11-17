
import joblib

model = joblib.load("freshsense_model.pkl")

def predict_freshness(rs_r0):
    prediction = model.predict([[rs_r0]])[0]

    probabilities = model.predict_proba([[rs_r0]])[0]
    confidence = max(probabilities) * 100

    return {
        "prediction": prediction,
        "confidence": round(confidence, 2)
    }


if __name__ == "__main__":
    result = predict_freshness(0.95)
    print("Prediction:", result["prediction"])
    print("Confidence:", result["confidence"], "%")
