
import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from dotenv import load_dotenv
from src.database import (
    initialize_database,
    log_activity,
    get_all_users,
    get_recent_activities
)
from src.auth import render_auth_screen, logout_user

# --------------------------------------------------
# 1. PROJECT PATHS AND CONFIGURATION
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "models"
REPORT_DIR = ROOT / "reports"
FIGURE_DIR = REPORT_DIR / "figures"

load_dotenv(ROOT / ".env")
API_KEY = os.getenv("COINGECKO_API_KEY")

BASE_URL = "https://api.coingecko.com/api/v3"

st.set_page_config(
    page_title="CryptoPulse",
    page_icon="₿",
    layout="wide"
)


# --------------------------------------------------
# USER AUTHENTICATION
# --------------------------------------------------

initialize_database()

if "current_user" not in st.session_state:
    render_auth_screen()
    st.stop()

current_user = st.session_state["current_user"]

st.sidebar.success(f"Logged in as: {current_user['username']}")

if st.sidebar.button("Logout", use_container_width=True):
    logout_user()
    # --------------------------------------------------
# ADMIN DASHBOARD
# --------------------------------------------------

if current_user["role"] == "admin":

    page = st.sidebar.radio(
        "Navigation",
        ["Market Dashboard", "Admin Dashboard"]
    )

    if page == "Admin Dashboard":

        st.title("🔐 Admin Dashboard")
        st.caption("Monitor registered users and their activity.")

        users = get_all_users()
        activities = get_recent_activities(limit=100)

        user_df = pd.DataFrame(users)
        activity_df = pd.DataFrame(activities)

        total_users = len(users)
        total_admins = sum(
            1 for user in users if user["role"] == "admin"
        )

        col1, col2, col3 = st.columns(3)

        col1.metric("Total Users", total_users)
        col2.metric("Admin Accounts", total_admins)
        col3.metric("Recent Activities", len(activities))

        st.divider()

        st.subheader("👥 Registered Users")

        if not user_df.empty:
            st.dataframe(
                user_df,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No registered users found.")

        st.divider()

        st.subheader("📋 Recent User Activities")

        if not activity_df.empty:

            st.dataframe(
                activity_df,
                use_container_width=True,
                hide_index=True
            )

            st.subheader("Activity Breakdown")

            activity_counts = activity_df["action"].value_counts()
            st.bar_chart(activity_counts)

        else:
            st.info("No activity has been recorded yet.")

        st.stop()

# --------------------------------------------------
# 2. HELPER FUNCTIONS
# --------------------------------------------------

def money(value):
    if value is None or pd.isna(value):
        return "N/A"
    return f"${value:,.2f}"


def compact_money(value):
    if value is None or pd.isna(value):
        return "N/A"

    value = float(value)

    if abs(value) >= 1_000_000_000_000:
        return f"${value / 1_000_000_000_000:.2f}T"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"

    return f"${value:,.2f}"


def read_csv(path):
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def api_request(endpoint, params=None):
    headers = {}

    if API_KEY:
        headers["x-cg-demo-api-key"] = API_KEY

    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        headers=headers,
        params=params,
        timeout=20
    )
    response.raise_for_status()
    return response.json()


# --------------------------------------------------
# 3. FETCH LIVE MARKET DATA
# --------------------------------------------------


@st.cache_data(ttl=300)
def get_global_data():
    try:
        data = api_request("global")
        return data, "LIVE API"
    except Exception:
        saved_file = RAW_DIR / "global_market.json"

        if saved_file.exists():
            with open(saved_file, "r", encoding="utf-8") as file:
                return json.load(file), "SAVED DATA"

        return None, "UNAVAILABLE"


@st.cache_data(ttl=300)
def get_market_data():
    try:
        data = api_request(
            "coins/markets",
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 20,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h"
            }
        )
        return data, "LIVE API"

    except Exception:
        saved_data = read_csv(RAW_DIR / "market_data.csv")
        if not saved_data.empty:
            return saved_data.to_dict(orient="records"), "SAVED DATA"

        return [], "UNAVAILABLE"


@st.cache_data(ttl=300)
def get_trending_data():
    try:
        result = api_request("search/trending")
        coins = result.get("coins", [])
        data = [item.get("item", {}) for item in coins]
        return data, "LIVE API"

    except Exception:
        saved_data = read_csv(RAW_DIR / "trending_coins.csv")
        if not saved_data.empty:
            return saved_data.to_dict(orient="records"), "SAVED DATA"

        return [], "UNAVAILABLE"


# --------------------------------------------------
# 4. LOAD HISTORICAL BITCOIN DATA
# --------------------------------------------------

def get_bitcoin_history():
    path = PROCESSED_DIR / "bitcoin_cleaned.csv"

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df = df.sort_values("date")

    return df


# --------------------------------------------------
# 5. LOAD MACHINE LEARNING MODEL
# --------------------------------------------------

def get_prediction():
    model_path = MODEL_DIR / "bitcoin_model.pkl"
    history = get_bitcoin_history()

    if not model_path.exists():
        return None, "Trained model file not found."

    if history.empty:
        return None, "Bitcoin historical data not found."

    try:
        bundle = joblib.load(model_path)

        model = bundle["model"]
        feature_columns = bundle["feature_columns"]

        data = history.copy()

        # Re-create the same lag features used during training.
        data["price_lag_1"] = data["price"].shift(1)
        data["price_lag_2"] = data["price"].shift(2)
        data["price_lag_3"] = data["price"].shift(3)
        data["price_lag_7"] = data["price"].shift(7)
        data["price_lag_14"] = data["price"].shift(14)
        data["price_lag_30"] = data["price"].shift(30)

        data["return_lag_1"] = data["daily_return"].shift(1)
        data["return_lag_7"] = data["daily_return"].shift(7)

        data["moving_average_7_lag_1"] = (
            data["moving_average_7"].shift(1)
        )
        data["moving_average_30_lag_1"] = (
            data["moving_average_30"].shift(1)
        )

        if "volume" in data.columns:
            data["volume_lag_1"] = data["volume"].shift(1)

        if "market_cap" in data.columns:
            data["market_cap_lag_1"] = data["market_cap"].shift(1)

        latest = data.dropna(subset=feature_columns).iloc[[-1]]
        X_latest = latest[feature_columns]

        prediction = float(model.predict(X_latest)[0])

        return {
            "prediction": prediction,
            "latest_price": float(history["price"].iloc[-1]),
            "date": history["date"].iloc[-1]
            if "date" in history.columns else None
        }, None

    except Exception as error:
        return None, str(error)


# --------------------------------------------------
# 6. DASHBOARD HEADER
# --------------------------------------------------

st.title("₿ CryptoPulse")
st.caption(
    "Cryptocurrency Analytics, Market Intelligence "
    "and Machine Learning Price Prediction"
)

# Fetch data and identify its source
global_result, global_source = get_global_data()
market_records, market_source = get_market_data()
trending_records, trending_source = get_trending_data()

st.subheader("Data Connection Status")

status_col1, status_col2, status_col3 = st.columns(3)

with status_col1:
    if global_source == "LIVE API":
        st.success("🟢 Global Market: LIVE API")
    elif global_source == "SAVED DATA":
        st.warning("🟡 Global Market: SAVED DATA")
    else:
        st.error("🔴 Global Market: UNAVAILABLE")

with status_col2:
    if market_source == "LIVE API":
        st.success("🟢 Coin Prices: LIVE API")
    elif market_source == "SAVED DATA":
        st.warning("🟡 Coin Prices: SAVED DATA")
    else:
        st.error("🔴 Coin Prices: UNAVAILABLE")

with status_col3:
    if trending_source == "LIVE API":
        st.success("🟢 Trending: LIVE API")
    elif trending_source == "SAVED DATA":
        st.warning("🟡 Trending: SAVED DATA")
    else:
        st.error("🔴 Trending: UNAVAILABLE")


if st.button("Refresh Market Data"):
    log_activity(
        current_user["id"],
        "MARKET_REFRESH",
        "User refreshed cryptocurrency market data"
    )

    get_global_data.clear()
    get_market_data.clear()
    get_trending_data.clear()
    st.rerun()

# --------------------------------------------------
# 7. GLOBAL MARKET STATISTICS
# --------------------------------------------------

st.header("Global Cryptocurrency Market")
global_info = (
    global_result.get("data", {})
    if global_result else {}
)

market_cap = global_info.get(
    "total_market_cap", {}
).get("usd")

volume = global_info.get(
    "total_volume", {}
).get("usd")

market_change = global_info.get(
    "market_cap_change_percentage_24h_usd"
)

active_coins = global_info.get("active_cryptocurrencies")

if global_info:
    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Market Cap",
        compact_money(market_cap),
        f"{market_change:.2f}%" if market_change is not None else None
    )

    col2.metric(
        "24h Trading Volume",
        compact_money(volume)
    )

    col3.metric(
        "Active Cryptocurrencies",
        f"{active_coins:,}" if active_coins is not None else "N/A"
    )

    col4.metric(
        "Markets",
        f"{global_info.get('markets', 'N/A')}"
    )
else:
    st.warning(
        "Global market data could not be loaded. "
        "Check your internet connection or API key."
    )


# --------------------------------------------------
# 8. MARKET OVERVIEW
# --------------------------------------------------
st.divider()
st.header("Cryptocurrency Market Overview")

market = pd.DataFrame(market_records)

if not market.empty:

    search = st.text_input(
        "Search cryptocurrency",
        placeholder="Search Bitcoin, Ethereum..."
    )

    # ACTIVITY TRACKING
    if search.strip():
        if search != st.session_state.get("last_logged_search"):
            log_activity(
                current_user["id"],
                "CRYPTO_SEARCH",
                f"Search query: {search.strip()[:50]}"
            )

            st.session_state["last_logged_search"] = search

    # FILTER SEARCH RESULTS
    if "name" in market.columns and search:
        market = market[
            market["name"].astype(str).str.contains(
                search, case=False, na=False
            )
        ]

    display_columns = [
        "market_cap_rank",
        "name",
        "symbol",
        "current_price",
        "price_change_percentage_24h",
        "market_cap",
        "total_volume"
    ]

    available_columns = [
        col for col in display_columns if col in market.columns
    ]

    st.dataframe(
        market[available_columns],
        use_container_width=True,
        hide_index=True
    )

else:
    st.warning("Market overview data is not available.")


# --------------------------------------------------
# 9. TRENDING CRYPTOCURRENCIES
# --------------------------------------------------

st.divider()
st.header("Trending Cryptocurrencies")

trending = pd.DataFrame(trending_records)
if not trending.empty:
    trending_columns = [
        col for col in
        ["name", "symbol", "market_cap_rank", "price_btc"]
        if col in trending.columns
    ]

    if trending_columns:
        st.dataframe(
            trending[trending_columns],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write(trending)
else:
    st.info("Trending cryptocurrency data is not available.")


# --------------------------------------------------
# 10. BITCOIN HISTORICAL ANALYSIS
# --------------------------------------------------

st.divider()
st.header("Bitcoin Historical Analytics")

history = get_bitcoin_history()

if not history.empty and "price" in history.columns:

    col1, col2, col3 = st.columns(3)

    latest_price = history["price"].iloc[-1]
    highest_price = history["price"].max()
    lowest_price = history["price"].min()

    col1.metric("Latest Historical Price", money(latest_price))
    col2.metric("Highest Recorded Price", money(highest_price))
    col3.metric("Lowest Recorded Price", money(lowest_price))

    if "date" in history.columns:
        price_chart = px.line(
            history,
            x="date",
            y="price",
            title="Bitcoin Historical Price Trend",
            labels={
                "date": "Date",
                "price": "Bitcoin Price (USD)"
            }
        )

        price_chart.update_layout(
            template="plotly_dark",
            hovermode="x unified"
        )

        st.plotly_chart(price_chart, use_container_width=True)

    if "moving_average_7" in history.columns:
        ma_chart = go.Figure()

        ma_chart.add_trace(go.Scatter(
            x=history["date"],
            y=history["price"],
            name="Bitcoin Price"
        ))

        ma_chart.add_trace(go.Scatter(
            x=history["date"],
            y=history["moving_average_7"],
            name="7-Day Moving Average"
        ))

        ma_chart.add_trace(go.Scatter(
            x=history["date"],
            y=history["moving_average_30"],
            name="30-Day Moving Average"
        ))

        ma_chart.update_layout(
            title="Bitcoin Price and Moving Averages",
            template="plotly_dark",
            hovermode="x unified"
        )

        st.plotly_chart(ma_chart, use_container_width=True)

else:
    st.warning(
        "Historical Bitcoin dataset not found. "
        "Run the data preprocessing phase first."
    )


# --------------------------------------------------
# 11. MACHINE LEARNING PRICE PREDICTION
# --------------------------------------------------

st.divider()
st.header("Bitcoin Price Prediction")

prediction_result, prediction_error = get_prediction()
if prediction_result and not st.session_state.get("prediction_logged"):
    log_activity(
        current_user["id"],
        "PREDICTION_VIEW",
        "User viewed Bitcoin price prediction"
    )

    st.session_state["prediction_logged"] = True

if prediction_result:

    col1, col2, col3 = st.columns(3)

    current_price = prediction_result["latest_price"]
    predicted_price = prediction_result["prediction"]

    difference = predicted_price - current_price
    percentage = (
        difference / current_price * 100
        if current_price else 0
    )

    col1.metric(
        "Latest Historical Price",
        money(current_price)
    )

    col2.metric(
        "Predicted Next Price",
        money(predicted_price),
        f"{percentage:+.2f}%"
    )

    col3.metric(
        "Predicted Price Difference",
        money(difference)
    )

    st.info(
        "This is an experimental machine learning estimate, "
        "not a guaranteed future price or financial advice."
    )

else:
    st.error(f"Prediction could not be generated: {prediction_error}")


# --------------------------------------------------
# 12. MODEL PERFORMANCE
# --------------------------------------------------

st.divider()
st.header("Machine Learning Model Performance")

metrics_path = REPORT_DIR / "model_metrics.json"

if metrics_path.exists():

    with open(metrics_path, "r", encoding="utf-8") as file:
        metrics = json.load(file)

    st.write("Evaluation results from the trained Random Forest model:")

    st.json(metrics)

else:
    st.warning("Model evaluation metrics file was not found.")


# Show the saved actual vs predicted chart.

performance_chart = FIGURE_DIR / "actual_vs_predicted.png"

if performance_chart.exists():
    st.subheader("Actual vs Predicted Bitcoin Prices")
    st.image(
        str(performance_chart),
        use_container_width=True
    )


# --------------------------------------------------
# 13. FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "CryptoPulse | Built with Python, Streamlit, "
    "CoinGecko API, Pandas, Plotly and Scikit-learn"
)
