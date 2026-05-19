import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import os

os.makedirs("outputs/plots", exist_ok=True)

df = pd.read_csv("data/processed/ensemble_results.csv")
df = df.dropna()  # remove NaN rows


def plot_overall_prediction():
    plt.figure(figsize=(14, 5))
    plt.plot(df["true_cases"], label="True", linewidth=2)
    plt.plot(df["ensemble_pred"], label="Ensemble", alpha=0.8)
    plt.plot(df["xgb_pred"], label="XGB", alpha=0.6)
    plt.plot(df["lstm_pred"], label="LSTM", alpha=0.6)
    plt.legend()
    plt.title("Dengue Forecasting – Actual vs Predicted")
    plt.xlabel("Weeks")
    plt.ylabel("Cases")
    plt.grid(True)
    plt.savefig("outputs/plots/overall_timeseries.png", dpi=300)
    plt.close()


def plot_error_distribution():
    error = df["ensemble_pred"] - df["true_cases"]
    plt.figure(figsize=(9, 5))
    plt.hist(error, bins=25, alpha=0.7)
    plt.title("Ensemble Error Distribution")
    plt.xlabel("Error")
    plt.ylabel("Frequency")
    plt.grid(True)
    plt.savefig("outputs/plots/error_distribution.png", dpi=300)
    plt.close()


def plot_confusion_matrix():
    pred_risk = np.where(df["ensemble_pred"] < 5, 0,
                 np.where(df["ensemble_pred"] < 10, 1, 2))
    
    true_risk = np.where(df["true_cases"] < 5, 0,
                 np.where(df["true_cases"] < 10, 1, 2))

    cm = confusion_matrix(true_risk, pred_risk)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm)
    disp.plot()
    plt.title("Risk Level Confusion Matrix")
    plt.savefig("outputs/plots/confusion_matrix.png", dpi=300)
    plt.close()


def plot_per_district(district_name):
    d = df[df["district"] == district_name]

    plt.figure(figsize=(14, 5))
    plt.plot(d["true_cases"], label="True")
    plt.plot(d["ensemble_pred"], label="Ensemble")
    plt.title(f"{district_name} – Prediction vs Actual")
    plt.legend()
    plt.grid(True)
    fname = district_name.replace(" ", "_")
    plt.savefig(f"outputs/plots/{fname}_timeseries.png", dpi=300)
    plt.close()


if __name__ == "__main__":
    print("Saving all graphs to outputs/plots/ ...")

    plot_overall_prediction()
    plot_error_distribution()
    plot_confusion_matrix()

    unique = df["district"].unique()
    for dist in unique:
        plot_per_district(dist)

    print("All plots saved successfully!")