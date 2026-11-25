"""Loan Application Service: stores loan applications and scores their default risk."""
from contextlib import asynccontextmanager

import os

import mlflow
import pandas as pd
from fastapi import FastAPI, HTTPException
from mlflow import MlflowClient

from schemas import Application, ApplicationCreate, LoanFeatures, Prediction

ml = {}            # filled at start-up: {"model": ..., "version": ...}
APPLICATIONS = {}  # in-memory store; resets when the server restarts
FEATURES = ["amount_usd", "term_months", "monthly_income_usd", "previous_loans", "late_payments"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model once, when the server starts, from the MLflow registry BY ALIAS.
    # Moving the alias in the registry and restarting is enough to change (or roll back) the model.
    name = os.getenv("MODEL_NAME", "loan-default")
    alias = os.getenv("MODEL_ALIAS", "champion")
    ml["model"] = mlflow.pyfunc.load_model(f"models:/{name}@{alias}")
    ml["version"] = str(MlflowClient().get_model_version_by_alias(name, alias).version)
    yield
    ml.clear()


app = FastAPI(title="Loan Application Service", version="1.0.0", lifespan=lifespan)


def score(features: LoanFeatures) -> Prediction:
    X = pd.DataFrame([features.model_dump()])[FEATURES]
    probability = float(ml["model"].predict(X)[0, 1])  # column 1 = probability of default
    band = "low" if probability < 0.2 else "medium" if probability < 0.5 else "high"
    return Prediction(default_probability=round(probability, 3), risk_band=band, model_version=ml["version"])


@app.get("/health")
def health():
    return {"status": "ok", "model_version": ml.get("version")}


@app.post("/api/v1/predictions", response_model=Prediction)
def predict(features: LoanFeatures):
    return score(features)


@app.post("/api/v1/applications", response_model=Application, status_code=201)
def create_application(body: ApplicationCreate):
    new = Application(id=7781 + len(APPLICATIONS), status="pending",
                      prediction=score(body), **body.model_dump())
    APPLICATIONS[new.id] = new
    return new


@app.get("/api/v1/applications", response_model=list[Application])
def list_applications():
    return list(APPLICATIONS.values())


@app.get("/api/v1/applications/{application_id}", response_model=Application)
def get_application(application_id: int):
    if application_id not in APPLICATIONS:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return APPLICATIONS[application_id]
