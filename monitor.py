"""Simulate 14 days of production traffic and log drift metrics to MLflow."""
import mlflow

from data import FEATURES, make_data
from psi import psi

reference = make_data(n=5000, seed=42)  # the training data
model = mlflow.pyfunc.load_model("models:/loan-default@champion")

mlflow.set_experiment("loan-default-monitoring")
with mlflow.start_run(run_name="daily-drift-check"):
    for day in range(1, 15):
        # Each day: 400 applications; incomes fall by 8 USD a day and requested amounts creep up.
        today = make_data(n=400, seed=100 + day, income_mean=400 - 8 * day, amount_high=5001 + 100 * day)
        scores = {}
        for feature in ["monthly_income_usd", "amount_usd", "late_payments"]:
            scores[feature] = psi(reference[feature], today[feature])
            mlflow.log_metric(f"psi_{feature}", scores[feature], step=day)
        predicted = float(model.predict(today[FEATURES])[:, 1].mean())
        actual = float(today.defaulted.mean())
        mlflow.log_metric("mean_predicted_default", predicted, step=day)
        mlflow.log_metric("actual_default_rate", actual, step=day)
        print(f"day {day:>2}  psi_income={scores['monthly_income_usd']:.3f}  psi_amount={scores['amount_usd']:.3f}  "
              f"psi_late={scores['late_payments']:.3f}  mean_predicted_default={predicted:.3f}  "
              f"actual_default_rate={actual:.3f}")
