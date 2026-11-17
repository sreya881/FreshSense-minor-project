
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.metrics import accuracy_score, f1_score

df = pd.read_csv("Dataframe_ML_complete.csv", sep=";")

def get_class(day):
    if day <= 5:
        return "fresh"
    elif day <= 10:
        return "moderate"
    return "spoiled"

df["label"] = df["Storage Day"].apply(get_class)

X = df[["MQ135"]]
y = df["label"]
groups = df["Storage Scenario"]

model = RandomForestClassifier(
    n_estimators=200,
    max_depth=2,
    min_samples_leaf=3,
    class_weight="balanced",
    random_state=42
)

# Evaluate by storage scenario
logo = LeaveOneGroupOut()
actual = []
predicted = []

for train, test in logo.split(X, y, groups):
    model.fit(X.iloc[train], y.iloc[train])
    p = model.predict(X.iloc[test])

    actual.extend(y.iloc[test])
    predicted.extend(p)

print("Accuracy:",
      accuracy_score(actual, predicted) * 100)

print("Macro F1:",
      f1_score(actual, predicted, average="macro"))

# Train final model
model.fit(X, y)

joblib.dump(model, "freshsense_model.pkl")

print("Model saved successfully!")
