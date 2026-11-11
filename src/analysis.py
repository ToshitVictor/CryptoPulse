
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from pathlib import Path

# ----------------------------------
# 1. PROJECT PATHS
# ----------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATA_FILE = PROJECT_ROOT / "data" / "processed" / "bitcoin_cleaned.csv"

FIGURE_DIR = PROJECT_ROOT / "reports" / "figures"
FIGURE_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------
# 2. LOAD DATA
# ----------------------------------

def load_data():

    print("\nLoading processed Bitcoin data...")

    if not DATA_FILE.exists():
        raise FileNotFoundError(
            "Cleaned CSV not found. Run Phase 4 first: "
            "python -m src.data_processing"
        )

    df = pd.read_csv(DATA_FILE)

    df["date"] = pd.to_datetime(df["date"], utc=True)

    df = df.sort_values("date").reset_index(drop=True)

    print("Data loaded successfully!")

    print("\nDataset shape:", df.shape)

    return df


# ----------------------------------
# 3. BASIC STATISTICAL ANALYSIS
# ----------------------------------

def statistical_analysis(df):

    print("\n========== STATISTICAL ANALYSIS ==========")

    print("\nDataset information:")
    df.info()

    print("\nStatistical summary:")
    print(df.describe())

    print("\nBitcoin Price Statistics:")

    print("Average price:", df["price"].mean())
    print("Highest price:", df["price"].max())
    print("Lowest price:", df["price"].min())
    print("Median price:", df["price"].median())

    print("\nDate range:")
    print("Start:", df["date"].min())
    print("End:", df["date"].max())

    if "daily_return" in df.columns:
        print("\nDaily return statistics:")
        print("Highest daily return:", df["daily_return"].max())
        print("Lowest daily return:", df["daily_return"].min())


# ----------------------------------
# 4. SAVE CHART FUNCTION
# ----------------------------------

def save_chart(fig, filename):

    output_path = FIGURE_DIR / filename

    fig.tight_layout()

    fig.savefig(output_path, dpi=150, bbox_inches="tight")

    plt.close(fig)

    print("Chart saved:", output_path)


# ----------------------------------
# 5. HISTORICAL PRICE TREND
# ----------------------------------

def price_trend(df):

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(df["date"], df["price"], label="Bitcoin Price")

    ax.set_title("Bitcoin Historical Price Trend")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (USD)")

    ax.legend()
    ax.grid(True, alpha=0.3)

    save_chart(fig, "price_trend.png")


# ----------------------------------
# 6. TRADING VOLUME
# ----------------------------------

def trading_volume(df):

    if "volume" not in df.columns:
        print("Volume column unavailable. Skipping volume chart.")
        return

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(df["date"], df["volume"], label="Trading Volume")

    ax.set_title("Bitcoin Trading Volume Over Time")
    ax.set_xlabel("Date")
    ax.set_ylabel("Volume (USD)")

    ax.legend()
    ax.grid(True, alpha=0.3)

    save_chart(fig, "trading_volume.png")


# ----------------------------------
# 7. DAILY RETURNS
# ----------------------------------

def daily_returns(df):

    if "daily_return" not in df.columns:
        print("Daily return column unavailable.")
        return

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(
        df["date"],
        df["daily_return"],
        label="Daily Return"
    )

    ax.axhline(y=0, linestyle="--")

    ax.set_title("Bitcoin Daily Returns")
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily Return (%)")

    ax.legend()
    ax.grid(True, alpha=0.3)

    save_chart(fig, "daily_returns.png")


# ----------------------------------
# 8. MOVING AVERAGES
# ----------------------------------

def moving_averages(df):

    required = ["moving_average_7", "moving_average_30"]

    if not all(column in df.columns for column in required):
        print("Moving average columns unavailable.")
        return

    fig, ax = plt.subplots(figsize=(12, 5))

    ax.plot(df["date"], df["price"], label="Actual Price", alpha=0.5)

    ax.plot(
        df["date"],
        df["moving_average_7"],
        label="7-Day Moving Average"
    )

    ax.plot(
        df["date"],
        df["moving_average_30"],
        label="30-Day Moving Average"
    )

    ax.set_title("Bitcoin Price and Moving Averages")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price (USD)")

    ax.legend()
    ax.grid(True, alpha=0.3)

    save_chart(fig, "moving_averages.png")


# ----------------------------------
# 9. PRICE DISTRIBUTION
# ----------------------------------

def price_distribution(df):

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.hist(df["price"], bins=30, edgecolor="black")

    ax.set_title("Bitcoin Price Distribution")
    ax.set_xlabel("Price (USD)")
    ax.set_ylabel("Frequency")

    ax.grid(True, alpha=0.3)

    save_chart(fig, "price_distribution.png")


# ----------------------------------
# 10. CORRELATION HEATMAP
# ----------------------------------

def correlation_heatmap(df):

    columns = [
        "price",
        "volume",
        "market_cap",
        "daily_return",
        "moving_average_7",
        "moving_average_30",
        "price_difference"
    ]

    available_columns = [
        column for column in columns
        if column in df.columns
    ]

    correlation = df[available_columns].corr()

    fig, ax = plt.subplots(figsize=(10, 7))

    image = ax.imshow(
        correlation,
        cmap="coolwarm",
        vmin=-1,
        vmax=1
    )

    ax.set_xticks(range(len(available_columns)))
    ax.set_yticks(range(len(available_columns)))

    ax.set_xticklabels(available_columns, rotation=45, ha="right")
    ax.set_yticklabels(available_columns)

    for i in range(len(available_columns)):
        for j in range(len(available_columns)):
            ax.text(
                j,
                i,
                f"{correlation.iloc[i, j]:.2f}",
                ha="center",
                va="center"
            )

    ax.set_title("Bitcoin Market Data Correlation Heatmap")

    fig.colorbar(image, ax=ax, label="Correlation")

    save_chart(fig, "correlation_heatmap.png")


# ----------------------------------
# 11. MAIN FUNCTION
# ----------------------------------

def main():

    print("=" * 50)
    print("       CRYPTOPULSE EXPLORATORY DATA ANALYSIS")
    print("=" * 50)

    df = load_data()

    statistical_analysis(df)

    print("\nGenerating visualizations...")

    price_trend(df)
    trading_volume(df)
    daily_returns(df)
    moving_averages(df)
    price_distribution(df)
    correlation_heatmap(df)

    print("\n" + "=" * 50)
    print("EDA COMPLETED SUCCESSFULLY!")
    print("All available charts are saved in reports/figures/")
    print("=" * 50)


if __name__ == "__main__":
    main()
