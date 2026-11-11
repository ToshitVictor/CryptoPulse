
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_FILE = PROJECT_ROOT / "data" / "raw" / "bitcoin_history.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_data():

    print("\n1. Loading Bitcoin historical data...")

    if not RAW_FILE.exists():
        raise FileNotFoundError(
            "Bitcoin history CSV not found. "
            "Run python -m src.api first."
        )

    df = pd.read_csv(RAW_FILE)

    print("Data loaded successfully!")

    return df


def inspect_data(df):

    print("\n2. Inspecting raw data...")

    print("\nFirst five records:")
    print(df.head())

    print("\nDataset shape:")
    print(df.shape)

    print("\nColumn information:")
    df.info()

    print("\nMissing values:")
    print(df.isnull().sum())

    print("\nDuplicate records:")
    print(df.duplicated().sum())


def clean_data(df):

    print("\n3. Cleaning the dataset...")

    df["price"] = pd.to_numeric(
        df["price"], errors="coerce"
    )

    df = df.dropna(subset=["price"])

    df = df[df["price"] > 0]

    if "timestamp" in df.columns:
        df = df.drop_duplicates(subset=["timestamp"])
    else:
        df = df.drop_duplicates()

    if "date" in df.columns:
        df["date"] = pd.to_datetime(
            df["date"], errors="coerce", utc=True
        )

        df = df.dropna(subset=["date"])

    numeric_columns = ["volume", "market_cap"]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column], errors="coerce"
            )

            df[column] = df[column].replace(
                [np.inf, -np.inf], np.nan
            )

            df[column] = df[column].interpolate(
                limit_direction="both"
            )

    if "date" in df.columns:
        df = df.sort_values("date")

    df = df.reset_index(drop=True)

    print("Data cleaning completed!")

    return df


def feature_engineering(df):

    print("\n4. Creating additional features...")

    df["daily_return"] = df["price"].pct_change() * 100

    df["moving_average_7"] = (
        df["price"].rolling(window=7).mean()
    )

    df["moving_average_30"] = (
        df["price"].rolling(window=30).mean()
    )

    df["price_difference"] = df["price"].diff()

    print("Additional features created!")

    return df


def save_processed_data(df):

    print("\n5. Saving processed dataset...")

    output_file = PROCESSED_DIR / "bitcoin_cleaned.csv"

    df.to_csv(output_file, index=False)

    print(f"Cleaned dataset saved at: {output_file}")


def main():

    print("=" * 45)
    print("    CRYPTOPULSE DATA PREPROCESSING")
    print("=" * 45)

    df = load_data()

    inspect_data(df)

    df = clean_data(df)

    df = feature_engineering(df)

    df = df.replace([np.inf, -np.inf], np.nan)

    df = df.dropna(
        subset=[
            "daily_return",
            "moving_average_7",
            "moving_average_30",
            "price_difference"
        ]
    )

    save_processed_data(df)

    print("\nFinal dataset information:")
    df.info()

    print("\nFinal dataset preview:")
    print(df.head())

    print("\nPreprocessing completed successfully!")


if __name__ == "__main__":
    main()
