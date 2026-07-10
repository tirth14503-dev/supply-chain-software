from pathlib import Path

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, mean_absolute_error, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import features

ARTIFACT_DIR = Path(__file__).resolve().parent / 'artifacts'

DEMAND_CATEGORICAL = ['category']
DEMAND_NUMERIC = ['unit_price', 'reorder_point', 'month_sin', 'month_cos', 'lag1', 'lag2', 'lag3', 'rolling_mean_3']

RISK_CATEGORICAL = ['supplier_status']
RISK_NUMERIC = ['supplier_rating', 'supplier_lead_time', 'order_quantity', 'order_value', 'order_month']

DELAY_CATEGORICAL = ['carrier', 'shipment_type']
DELAY_NUMERIC = ['weight_kg', 'planned_transit_days', 'supplier_rating', 'supplier_lead_time', 'ship_month']


def _tree_preprocessor(categorical, numeric):
    return ColumnTransformer([
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical),
        ('num', 'passthrough', numeric),
    ])


def _linear_preprocessor(categorical, numeric):
    # linear models need scaled numeric features to converge and to be regularized fairly
    return ColumnTransformer([
        ('cat', OneHotEncoder(handle_unknown='ignore'), categorical),
        ('num', StandardScaler(), numeric),
    ])


def _mape(y_true, y_pred):
    denom = np.maximum(y_true, 5)
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100)


def train_demand_forecast(log):
    """RandomForest trained on the ratio (actual / recent rolling average) rather than raw
    quantity, since products span wildly different volume scales (4/mo vs 900/mo) — predicting
    a scale-free ratio and rescaling by the product's own rolling mean generalizes far better
    than predicting raw units directly."""
    X, y = features.build_demand_dataset()
    if len(X) < 20:
        log(f'  skipped (only {len(X)} rows, need >= 20)')
        return None
    ratio_y = y / X['rolling_mean_3'].clip(lower=1)
    X_train, X_test, y_train, y_test, ratio_train, _ = train_test_split(
        X, y, ratio_y, test_size=0.2, random_state=42
    )
    pipeline = Pipeline([
        ('pre', _tree_preprocessor(DEMAND_CATEGORICAL, DEMAND_NUMERIC)),
        ('model', RandomForestRegressor(n_estimators=200, max_depth=5, random_state=42)),
    ])
    pipeline.fit(X_train, ratio_train)
    pred_qty = pipeline.predict(X_test) * X_test['rolling_mean_3'].clip(lower=1)
    mae = mean_absolute_error(y_test, pred_qty)
    naive_mae = mean_absolute_error(y_test, X_test['lag1'])
    log(f'  rows={len(X)} test_MAE={mae:.1f} (naive last-month MAE={naive_mae:.1f}) '
        f'test_MAPE={_mape(y_test.values, pred_qty.values):.0f}% '
        f'(naive_MAPE={_mape(y_test.values, X_test["lag1"].values):.0f}%)')
    joblib.dump(pipeline, ARTIFACT_DIR / 'demand_forecast.joblib')
    return pipeline


def train_supplier_risk(log):
    X, y = features.build_supplier_risk_dataset()
    if len(X) < 20 or y.nunique() < 2:
        log(f'  skipped (only {len(X)} rows / {y.nunique()} classes)')
        return None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipeline = Pipeline([
        ('pre', _linear_preprocessor(RISK_CATEGORICAL, RISK_NUMERIC)),
        ('model', LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)),
    ])
    pipeline.fit(X_train, y_train)
    pred = pipeline.predict(X_test)
    proba = pipeline.predict_proba(X_test)[:, 1]
    log(f'  rows={len(X)} accuracy={accuracy_score(y_test, pred):.2f} '
        f'precision={precision_score(y_test, pred, zero_division=0):.2f} '
        f'recall={recall_score(y_test, pred, zero_division=0):.2f} '
        f'f1={f1_score(y_test, pred, zero_division=0):.2f} '
        f'roc_auc={roc_auc_score(y_test, proba):.2f}')
    joblib.dump(pipeline, ARTIFACT_DIR / 'supplier_risk.joblib')
    return pipeline


def train_delay_predictor(log):
    X, y = features.build_delay_dataset()
    if len(X) < 20 or y.nunique() < 2:
        log(f'  skipped (only {len(X)} rows / {y.nunique()} classes)')
        return None
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    pipeline = Pipeline([
        ('pre', _linear_preprocessor(DELAY_CATEGORICAL, DELAY_NUMERIC)),
        ('model', LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)),
    ])
    pipeline.fit(X_train, y_train)
    pred = pipeline.predict(X_test)
    proba = pipeline.predict_proba(X_test)[:, 1]
    log(f'  rows={len(X)} accuracy={accuracy_score(y_test, pred):.2f} '
        f'precision={precision_score(y_test, pred, zero_division=0):.2f} '
        f'recall={recall_score(y_test, pred, zero_division=0):.2f} '
        f'f1={f1_score(y_test, pred, zero_division=0):.2f} '
        f'roc_auc={roc_auc_score(y_test, proba):.2f}')
    joblib.dump(pipeline, ARTIFACT_DIR / 'delay_predictor.joblib')
    return pipeline


def train_anomaly_detector(log):
    X = features.build_anomaly_dataset()
    if len(X) < 20:
        log(f'  skipped (only {len(X)} rows, need >= 20)')
        return None
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('model', IsolationForest(n_estimators=200, contamination=0.05, random_state=42)),
    ])
    pipeline.fit(X)
    flagged = (pipeline.predict(X) == -1).sum()
    log(f'  rows={len(X)} flagged_as_anomaly={flagged} ({100 * flagged / len(X):.1f}%)')
    joblib.dump(pipeline, ARTIFACT_DIR / 'anomaly_detector.joblib')
    return pipeline


def train_all(log=print):
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    log('Training demand forecast model...')
    train_demand_forecast(log)
    log('Training supplier risk model...')
    train_supplier_risk(log)
    log('Training delay predictor model...')
    train_delay_predictor(log)
    log('Training anomaly detector model...')
    train_anomaly_detector(log)
