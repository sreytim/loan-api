"""Run with: pytest -v (uses model.joblib; with MLFLOW_TRACKING_URI set, uses loan-default@champion)"""
import pytest
from fastapi.testclient import TestClient

from main import APPLICATIONS, app

GOOD = {"amount_usd": 1500, "term_months": 12, "monthly_income_usd": 350.0, "previous_loans": 1, "late_payments": 0}


@pytest.fixture
def client():
    APPLICATIONS.clear()
    with TestClient(app) as c:  # "with" runs the lifespan, so the model is loaded
        yield c


def test_health_reports_model_version(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_version"]  # "1.0.0" from the file, or a registry version such as "1"


def test_prediction_is_a_probability(client):
    body = client.post("/api/v1/predictions", json=GOOD).json()
    assert 0 <= body["default_probability"] <= 1
    assert body["risk_band"] in {"low", "medium", "high"}


def test_amount_above_limit_is_rejected(client):
    assert client.post("/api/v1/predictions", json={**GOOD, "amount_usd": 9000}).status_code == 422


def test_create_and_read_application(client):
    created = client.post("/api/v1/applications", json={**GOOD, "borrower_id": 1042})
    assert created.status_code == 201
    app_id = created.json()["id"]
    assert client.get(f"/api/v1/applications/{app_id}").json()["borrower_id"] == 1042


def test_missing_application_is_404(client):
    assert client.get("/api/v1/applications/99999").status_code == 404


def test_api_routes_need_the_key_when_one_is_set(client, monkeypatch):
    monkeypatch.setattr("main.API_KEY", "test-key")
    assert client.get("/api/v1/applications").status_code == 401                               # no key
    assert client.get("/api/v1/applications", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/api/v1/applications", headers={"X-API-Key": "test-key"}).status_code == 200


def test_health_stays_open_when_a_key_is_set(client, monkeypatch):
    monkeypatch.setattr("main.API_KEY", "test-key")
    assert client.get("/health").status_code == 200  # Render's health check sends no key


RISKY = {"amount_usd": 4800, "term_months": 6, "monthly_income_usd": 250.0, "previous_loans": 0, "late_payments": 3}


def test_probability_is_the_chance_of_default_not_of_repayment(client):
    # Added after the bad release drill: score() once returned 1 - probability and every test still passed.
    safe = client.post("/api/v1/predictions", json=GOOD).json()
    risky = client.post("/api/v1/predictions", json=RISKY).json()
    assert safe["default_probability"] < 0.2 and safe["risk_band"] == "low"
    assert risky["default_probability"] > 0.8 and risky["risk_band"] == "high"
    assert risky["default_probability"] > safe["default_probability"]
