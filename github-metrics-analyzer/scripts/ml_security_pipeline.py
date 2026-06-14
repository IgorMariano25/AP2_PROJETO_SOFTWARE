"""Phase S7 - Machine Learning pipeline for security risk prediction.

Research question:
  "Can code quality metrics (complexity, duplication, code smells, process
   metrics, OO metrics) predict Java files prone to security risks?"

Design:
  - Problem: binary classification (has_security_risk)
  - Validation: GroupKFold(n_splits=5) grouped by repository
    → trains on N-1 repos, tests on the remaining one(s)
    → guards against intra-repo information leakage
  - Class imbalance: class_weight='balanced' + SMOTE on training folds
  - Evaluation: Precision, Recall, F1, ROC-AUC (NOT accuracy)
  - Models: LogisticRegression, DecisionTree, RandomForest,
            XGBoost, LightGBM
  - Feature importance: RandomForest Gini + SHAP (TreeExplainer)

Outputs (written to reports/):
  ml_results.csv          — per-model aggregate metrics
  ml_confusions.csv       — confusion matrix breakdown per model
  charts/roc_curves.png   — ROC curves (all models)
  charts/feature_importance_rf.png  — RF Gini importance
  charts/shap_summary.png — SHAP beeswarm (RandomForest)
  charts/model_comparison.png       — bar chart F1 / ROC-AUC
"""
from __future__ import annotations

import csv
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import DATA_DIR, REPORTS_DIR, CHARTS_DIR, get_logger

log = get_logger("ml")
warnings.filterwarnings("ignore")

TARGET = "has_security_risk"
SKIP_COLS = {"repository", "file", TARGET}

# ------------------------------------------------------------------ #
# Load & prepare dataset
# ------------------------------------------------------------------ #

def load_dataset() -> pd.DataFrame:
    path = DATA_DIR / "security_dataset.csv"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}. Run build_security_dataset.py first.")
    df = pd.read_csv(path, low_memory=False)
    log.info("Loaded dataset: %d rows × %d cols", len(df), len(df.columns))
    return df


def prepare(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """Return X, y, groups (repo labels), feature_names."""
    feature_cols = [c for c in df.columns if c not in SKIP_COLS]
    # Keep only numeric columns
    feature_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(df[c])]

    X = df[feature_cols].fillna(0).values.astype(np.float32)
    y = df[TARGET].values.astype(int)
    groups = df["repository"].values  # used for GroupKFold

    log.info("Features: %d  |  Positive labels: %d / %d  (%.1f%%)",
             len(feature_cols), y.sum(), len(y), 100 * y.mean())
    return X, y, groups, feature_cols


# ------------------------------------------------------------------ #
# Models
# ------------------------------------------------------------------ #

def build_models() -> dict:
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier
    from xgboost import XGBClassifier
    from lightgbm import LGBMClassifier

    return {
        "LogisticRegression": LogisticRegression(
            max_iter=1000, class_weight="balanced", random_state=42),
        "DecisionTree": DecisionTreeClassifier(
            max_depth=10, class_weight="balanced", random_state=42),
        "RandomForest": RandomForestClassifier(
            n_estimators=200, class_weight="balanced",
            n_jobs=-1, random_state=42),
        "XGBoost": XGBClassifier(
            n_estimators=200, scale_pos_weight=None,
            eval_metric="logloss", random_state=42,
            use_label_encoder=False, verbosity=0),
        "LightGBM": LGBMClassifier(
            n_estimators=200, class_weight="balanced",
            random_state=42, verbosity=-1),
    }


# ------------------------------------------------------------------ #
# Evaluation helpers
# ------------------------------------------------------------------ #

def _metrics(y_true, y_pred, y_prob) -> dict:
    from sklearn.metrics import (precision_score, recall_score, f1_score,
                                  roc_auc_score, confusion_matrix)
    labels = np.unique(y_true)
    if len(labels) < 2:
        return {"precision": 0, "recall": 0, "f1": 0, "roc_auc": 0,
                "tp": 0, "fp": 0, "fn": 0, "tn": 0}
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = (cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0))
    return {
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, y_prob),
        "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn),
    }


# ------------------------------------------------------------------ #
# GroupKFold cross-validation
# ------------------------------------------------------------------ #

def cross_validate(X, y, groups, feature_names: list[str]) -> dict:
    from sklearn.model_selection import GroupKFold
    from sklearn.preprocessing import StandardScaler
    from imblearn.over_sampling import SMOTE

    models = build_models()
    gkf = GroupKFold(n_splits=min(5, len(np.unique(groups))))

    results: dict[str, list] = {m: [] for m in models}
    roc_data: dict[str, list] = {m: [] for m in models}

    fold_idx = 0
    for train_idx, test_idx in gkf.split(X, y, groups):
        fold_idx += 1
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]

        test_repos = np.unique(groups[test_idx])
        log.info("Fold %d — test repos: %s  (train=%d test=%d pos_test=%d)",
                 fold_idx, test_repos, len(train_idx), len(test_idx), y_test.sum())

        if len(np.unique(y_test)) < 2:
            log.warning("  Fold %d skipped: only one class in test set", fold_idx)
            continue

        # Scale for linear models
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)

        # SMOTE on training fold (only if there are positives)
        if y_train.sum() > 1:
            try:
                sm = SMOTE(random_state=42, k_neighbors=min(5, y_train.sum() - 1))
                X_sm, y_sm = sm.fit_resample(X_train, y_train)
                X_sm_s, _ = sm.fit_resample(X_train_s, y_train)
            except Exception:
                X_sm, y_sm = X_train, y_train
                X_sm_s = X_train_s
        else:
            X_sm, y_sm = X_train, y_train
            X_sm_s = X_train_s

        for name, model in models.items():
            use_scaled = name in ("LogisticRegression",)
            Xtr = X_sm_s if use_scaled else X_sm
            Xte = X_test_s if use_scaled else X_test
            yr = y_sm

            try:
                model.fit(Xtr, yr)
                y_pred = model.predict(Xte)
                if hasattr(model, "predict_proba"):
                    y_prob = model.predict_proba(Xte)[:, 1]
                else:
                    y_prob = model.decision_function(Xte)
                m = _metrics(y_test, y_pred, y_prob)
                results[name].append(m)
                roc_data[name].append((y_test, y_prob))
            except Exception as exc:
                log.warning("  Model %s failed fold %d: %s", name, fold_idx, exc)

    return results, roc_data, models


# ------------------------------------------------------------------ #
# Aggregate and report
# ------------------------------------------------------------------ #

def aggregate_results(results: dict) -> pd.DataFrame:
    rows = []
    for model_name, folds in results.items():
        if not folds:
            continue
        keys = folds[0].keys()
        agg = {k: np.mean([f[k] for f in folds]) for k in keys}
        rows.append({"model": model_name, **{k: round(v, 4) for k, v in agg.items()}})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ #
# Plotting
# ------------------------------------------------------------------ #

COLORS = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#F44336"]


def plot_roc_curves(roc_data: dict, results_df: pd.DataFrame) -> None:
    from sklearn.metrics import roc_curve

    fig, ax = plt.subplots(figsize=(8, 6))
    for i, (model_name, folds) in enumerate(roc_data.items()):
        if not folds:
            continue
        all_y = np.concatenate([f[0] for f in folds])
        all_p = np.concatenate([f[1] for f in folds])
        fpr, tpr, _ = roc_curve(all_y, all_p)
        auc = results_df.loc[results_df["model"] == model_name, "roc_auc"]
        auc_val = float(auc.values[0]) if len(auc) else 0.0
        ax.plot(fpr, tpr, color=COLORS[i % len(COLORS)],
                label=f"{model_name} (AUC={auc_val:.3f})", lw=2)

    ax.plot([0, 1], [0, 1], "k--", lw=1)
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curves — GroupKFold (by repository)")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "roc_curves.png", dpi=150)
    plt.close(fig)
    log.info("Saved roc_curves.png")


def plot_model_comparison(results_df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, metric in zip(axes, ["f1", "roc_auc"]):
        vals = results_df.set_index("model")[metric].sort_values()
        bars = ax.barh(vals.index, vals.values,
                       color=[COLORS[i % len(COLORS)] for i in range(len(vals))])
        ax.set_xlabel(metric.upper().replace("_", "-"))
        ax.set_title(f"Mean {metric.upper()} (GroupKFold)")
        ax.set_xlim(0, 1)
        for bar, v in zip(bars, vals.values):
            ax.text(v + 0.005, bar.get_y() + bar.get_height() / 2,
                    f"{v:.3f}", va="center", fontsize=9)
    fig.suptitle("Model Comparison — Security Risk Prediction")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "model_comparison.png", dpi=150)
    plt.close(fig)
    log.info("Saved model_comparison.png")


def plot_feature_importance_rf(model, feature_names: list[str], top_n: int = 20) -> None:
    imp = model.feature_importances_
    idx = np.argsort(imp)[-top_n:]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh([feature_names[i] for i in idx], imp[idx], color="#2196F3")
    ax.set_xlabel("Gini Importance")
    ax.set_title(f"RandomForest — Top {top_n} Feature Importances")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "feature_importance_rf.png", dpi=150)
    plt.close(fig)
    log.info("Saved feature_importance_rf.png")


def plot_shap(model, X_sample: np.ndarray, feature_names: list[str]) -> None:
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)
        # For binary classification, take class 1 SHAP values
        if isinstance(shap_values, list) and len(shap_values) == 2:
            sv = shap_values[1]
        else:
            sv = shap_values

        fig, ax = plt.subplots(figsize=(10, 7))
        shap.summary_plot(sv, X_sample, feature_names=feature_names,
                          show=False, max_display=20)
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "shap_summary.png", dpi=150, bbox_inches="tight")
        plt.close()
        log.info("Saved shap_summary.png")
    except Exception as exc:
        log.warning("SHAP plot failed: %s", exc)


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def main() -> None:
    df = load_dataset()
    X, y, groups, feature_names = prepare(df)

    if len(np.unique(groups)) < 2:
        log.error("Need at least 2 repositories for GroupKFold. Aborting.")
        return
    if y.sum() == 0:
        log.error("No positive labels in dataset. Check Semgrep findings. Aborting.")
        return

    log.info("Starting GroupKFold cross-validation (%d repos)...",
             len(np.unique(groups)))
    results, roc_data, fitted_models = cross_validate(X, y, groups, feature_names)

    results_df = aggregate_results(results)
    log.info("\n%s", results_df.to_string(index=False))

    # Confusion matrix summary
    confusions = []
    for model_name, folds in results.items():
        for f in folds:
            confusions.append({"model": model_name, **f})

    # Save CSVs
    results_df.to_csv(REPORTS_DIR / "ml_results.csv", index=False)
    pd.DataFrame(confusions).to_csv(REPORTS_DIR / "ml_confusions.csv", index=False)
    log.info("Saved ml_results.csv and ml_confusions.csv")

    # Plots
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plot_roc_curves(roc_data, results_df)
    plot_model_comparison(results_df)

    # Train RF on full dataset for importance/SHAP
    from sklearn.ensemble import RandomForestClassifier
    rf_full = RandomForestClassifier(
        n_estimators=200, class_weight="balanced",
        n_jobs=-1, random_state=42)
    rf_full.fit(X, y)
    plot_feature_importance_rf(rf_full, feature_names)

    # SHAP on a sample (max 2000 rows for speed)
    sample_size = min(2000, len(X))
    rng = np.random.default_rng(42)
    idx_s = rng.choice(len(X), size=sample_size, replace=False)
    plot_shap(rf_full, X[idx_s], feature_names)

    log.info("ML pipeline complete.")
    _print_summary(results_df)


def _print_summary(df: pd.DataFrame) -> None:
    log.info("=" * 60)
    log.info("RESULTS SUMMARY")
    log.info("=" * 60)
    for _, row in df.iterrows():
        log.info("%-22s  F1=%.3f  ROC-AUC=%.3f  P=%.3f  R=%.3f",
                 row["model"], row["f1"], row["roc_auc"],
                 row["precision"], row["recall"])


if __name__ == "__main__":
    main()
