
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from pathlib import Path

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


# ----------------------------------
# 1. PROJECT PATHS
# ----------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_FILE = PROJECT_ROOT / "data" / "processed" / "bitcoin_cleaned.csv"

MODEL_DIR = PROJECT_ROOT / "models"
REPORT_DIR = PROJECT_ROOT / "reports"
FIGURE_DIR = REPORT_DIR / "figures"

MODEL_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------
# 2. LOAD DATA
# ----------------------------------

def load_data():

    print("\n1. Loading processed Bitcoin data...")

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            "Cleaned dataset not found. "
            "Run Phase 4 first."
        )

    df = pd.read_csv(DATA_FILE)

    df["date"] = pd.to_datetime(
        df["date"], errors="coerce", utc=True
    )

    df = df.dropna(subset=["date", "price"])

    df = df.sort_values("date").reset_index(drop=True)

    print("Dataset loaded successfully!")
    print("Number of records:", len(df))

    return df


# ----------------------------------
# 3. FEATURE ENGINEERING
# ----------------------------------

def prepare_features(df):

    print("\n2. Preparing machine learning features...")

    data = df.copy()

    # Previous price observations
    for lag in [1, 2, 3, 7, 14, 30]:

        data[f"price_lag_{lag}"] = data["price"].shift(lag)

    # Previous daily returns
    data["return_lag_1"] = data["daily_return"].shift(1)
    data["return_lag_7"] = data["daily_return"].shift(7)

    # Previous moving averages
    data["moving_average_7_lag_1"] = (
        data["moving_average_7"].shift(1)
    )

    data["moving_average_30_lag_1"] = (
        data["moving_average_30"].shift(1)
    )

    # Previous trading volume
    if "volume" in data.columns:
        data["volume_lag_1"] = data["volume"].shift(1)

    # Previous market capitalization
    if "market_cap" in data.columns:
        data["market_cap_lag_1"] = data["market_cap"].shift(1)

    # Target: next day's price
    data["target"] = data["price"].shift(-1)

    # Date of the target observation
    data["target_date"] = data["date"].shift(-1)

    feature_columns = [
        column for column in data.columns
        if column.endswith((
            "lag_1",
            "lag_2",
            "lag_3",
            "lag_7",
            "lag_14",
            "lag_30"
        ))
    ]

    # Remove rows containing missing feature or target values
    data = data.dropna(
        subset=feature_columns + ["target"]
    ).reset_index(drop=True)

    X = data[feature_columns]
    y = data["target"]

    print("Feature preparation completed!")
    print("Features:", feature_columns)
    print("Usable records:", len(data))

    return X, y, data, feature_columns


# ----------------------------------
# 4. CHRONOLOGICAL TRAIN-TEST SPLIT
# ----------------------------------

def split_data(X, y, data):

    print("\n3. Splitting training and testing data...")

    split_index = int(len(X) * 0.80)

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]

    test_dates = data["target_date"].iloc[split_index:]

    print("Training records:", len(X_train))
    print("Testing records:", len(X_test))

    return X_train, X_test, y_train, y_test, test_dates


# ----------------------------------
# 5. TRAIN RANDOM FOREST
# ----------------------------------

def train_model(X_train, y_train):

    print("\n4. Training Random Forest model...")

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=8,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    print("Model training completed!")

    return model


# ----------------------------------
# 6. EVALUATE MODEL
# ----------------------------------

def evaluate_model(model, X_test, y_test, X_train, y_train):

    print("\n5. Evaluating model...")

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)

    rmse = np.sqrt(
        mean_squared_error(y_test, predictions)
    )

    # Simple baseline: predict next price as current price
    baseline_predictions = X_test["price_lag_1"].values

    baseline_mae = mean_absolute_error(
        y_test, baseline_predictions
    )

    baseline_rmse = np.sqrt(
        mean_squared_error(y_test, baseline_predictions)
    )

    print("\nRandom Forest Results")
    print("---------------------")
    print("MAE:", round(mae, 2))
    print("RMSE:", round(rmse, 2))

    print("\nBaseline Results")
    print("----------------")
    print("MAE:", round(baseline_mae, 2))
    print("RMSE:", round(baseline_rmse, 2))

    metrics = {
        "model": "Random Forest Regressor",
        "mae": float(mae),
        "rmse": float(rmse),
        "baseline_mae": float(baseline_mae),
        "baseline_rmse": float(baseline_rmse),
        "training_records": int(len(X_train)),
        "testing_records": int(len(X_test))
    }

    with open(REPORT_DIR / "model_metrics.json", "w") as file:
        json.dump(metrics, file, indent=4)

    return predictions, metrics


# ----------------------------------
# 7. ACTUAL VS PREDICTED CHART
# ----------------------------------

def plot_predictions(y_test, predictions, test_dates):

    print("\n6. Creating prediction comparison chart...")

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        test_dates,
        y_test.values,
        label="Actual Price"
    )

    ax.plot(
        test_dates,
        predictions,
        label="Predicted Price"
    )

    ax.set_title("Bitcoin Actual vs Predicted Prices")

    ax.set_xlabel("Date")
    ax.set_ylabel("Price (USD)")

    ax.legend()
    ax.grid(True, alpha=0.3)

    fig.tight_layout()

    fig.savefig(
        FIGURE_DIR / "actual_vs_predicted.png",
        dpi=150,
        bbox_inches="tight"
    )

    plt.close(fig)

    print("Prediction comparison chart saved!")


# ----------------------------------
# 8. SAVE TRAINED MODEL
# ----------------------------------

def save_model(model, feature_columns):

    print("\n7. Saving trained model...")

    model_bundle = {
        "model": model,
        "feature_columns": feature_columns
    }

    model_path = MODEL_DIR / "bitcoin_model.pkl"

    joblib.dump(model_bundle, model_path)

    print("Trained model saved at:", model_path)


# ----------------------------------
# 9. PREDICT NEXT DAY PRICE
# ----------------------------------

def predict_next_day(model, X):

    print("\n8. Predicting next-day Bitcoin price...")

    latest_data = X.iloc[[-1]]

    predicted_price = model.predict(latest_data)[0]

    print(
        "Estimated next-day Bitcoin price: $",
        round(predicted_price, 2)
    )

    return predicted_price


# ----------------------------------
# 10. MAIN FUNCTION
# ----------------------------------

def main():

    print("=" * 50)
    print("       CRYPTOPULSE MACHINE LEARNING")
    print("=" * 50)

    df = load_data()

    X, y, data, feature_columns = prepare_features(df)

    if len(X) < 20:
        raise ValueError(
            "Not enough historical records to train and test the model."
        )

    X_train, X_test, y_train, y_test, test_dates = (
        split_data(X, y, data)
    )

    model = train_model(X_train, y_train)

    predictions, metrics = evaluate_model(
        model, X_test, y_test, X_train, y_train
    )

    plot_predictions(y_test, predictions, test_dates)

    save_model(model, feature_columns)

    predict_next_day(model, X, )

    print("\n" + "=" * 50)
    print("MACHINE LEARNING COMPLETED!")
    print("=" * 50)


if __name__ == "__main__":
    main()
