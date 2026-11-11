
import os
import json
import requests
import pandas as pd

from pathlib import Path
from dotenv import load_dotenv

# Load API key from the .env file
load_dotenv()

API_KEY = os.getenv("COINGECKO_API_KEY")

BASE_URL = "https://api.coingecko.com/api/v3"

# API headers
HEADERS = {}

if API_KEY:
    HEADERS["x-cg-demo-api-key"] = API_KEY

# Project data directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DATA = PROJECT_ROOT / "data" / "raw"

RAW_DATA.mkdir(parents=True, exist_ok=True)


def make_api_request(endpoint, params=None):
    """
    Connect to CoinGecko and retrieve API data.
    """

    url = f"{BASE_URL}/{endpoint}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        return response.json()

    except requests.exceptions.RequestException as error:
        print(f"API connection failed: {error}")
        return None


def fetch_global_data():
    print("\nFetching global market statistics...")

    data = make_api_request("global")

    if data:
        global_data = data.get("data", {})

        with open(
            RAW_DATA / "global_market.json",
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(global_data, file, indent=4)

        print("Global market data saved successfully!")

        return global_data

    return None


def fetch_market_data():
    print("\nFetching cryptocurrency market data...")

    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 20,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h"
    }

    data = make_api_request("coins/markets", params)

    if data:
        df = pd.DataFrame(data)

        df.to_csv(
            RAW_DATA / "market_data.csv",
            index=False
        )

        print("Market data saved successfully!")

        return df

    return None


def fetch_trending_data():
    print("\nFetching trending cryptocurrencies...")

    data = make_api_request("search/trending")

    if data:
        coins = data.get("coins", [])

        trending = []

        for item in coins:

            coin = item.get("item", {})

            trending.append({
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "market_cap_rank": coin.get("market_cap_rank"),
                "price_btc": coin.get("price_btc")
            })

        df = pd.DataFrame(trending)

        df.to_csv(
            RAW_DATA / "trending_coins.csv",
            index=False
        )

        print("Trending data saved successfully!")

        return df

    return None


def fetch_bitcoin_history():
    print("\nFetching Bitcoin historical prices...")

    params = {
        "vs_currency": "usd",
        "days": "365",
        "interval": "daily"
    }

    data = make_api_request(
        "coins/bitcoin/market_chart",
        params
    )

    if data and data.get("prices"):

        prices = pd.DataFrame(
            data["prices"],
            columns=["timestamp", "price"]
        )

        prices["date"] = pd.to_datetime(
            prices["timestamp"],
            unit="ms",
            utc=True
        )

        if data.get("total_volumes"):
            volumes = pd.DataFrame(
                data["total_volumes"],
                columns=["timestamp", "volume"]
            )

            prices = prices.merge(
                volumes,
                on="timestamp",
                how="left"
            )

        if data.get("market_caps"):
            caps = pd.DataFrame(
                data["market_caps"],
                columns=["timestamp", "market_cap"]
            )

            prices = prices.merge(
                caps,
                on="timestamp",
                how="left"
            )

        prices.to_csv(
            RAW_DATA / "bitcoin_history.csv",
            index=False
        )

        print("Bitcoin historical data saved successfully!")

        return prices

    return None


if __name__ == "__main__":

    print("=" * 45)
    print("       CRYPTOPULSE DATA COLLECTION")
    print("=" * 45)

    fetch_global_data()

    fetch_market_data()

    fetch_trending_data()

    fetch_bitcoin_history()
    params = {
    "vs_currency": "usd",
    "days": "365"
}

    print("\nData collection process completed!")
