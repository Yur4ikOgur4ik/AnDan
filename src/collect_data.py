from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

CBR_CURRENCY_DICT_URL = "https://www.cbr.ru/scripts/XML_valFull.asp"
CBR_DYNAMIC_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp"
WORLD_BANK_URL = "https://api.worldbank.org/v2/country/RUS/indicator/{indicator}"

START_DATE = date(2014, 1, 1)
END_DATE = date(2026, 6, 12)

TARGET_CURRENCY_CODES = ["USD", "EUR", "CNY", "GBP", "JPY", "CHF", "TRY", "KZT"]

WORLD_BANK_INDICATORS = {
    "FP.CPI.TOTL.ZG": "inflation_consumer_prices_pct",
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
    "PA.NUS.FCRF": "official_exchange_rate_lcu_per_usd",
}


@dataclass(frozen=True)
class CurrencyMeta:
    currency_id: str
    char_code: str
    name: str
    nominal: int


def ensure_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def fetch_url(url: str, params: dict[str, str] | None = None) -> requests.Response:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; HSE-data-analysis-project/1.0)"
    }
    response = requests.get(url, params=params, headers=headers, timeout=60)
    response.raise_for_status()
    return response


def parse_cbr_date(value: str) -> pd.Timestamp:
    return pd.to_datetime(value, format="%d.%m.%Y")


def parse_cbr_float(value: str) -> float:
    return float(value.replace(",", "."))


def format_cbr_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def load_currency_dictionary() -> pd.DataFrame:
    response = fetch_url(CBR_CURRENCY_DICT_URL)
    root = ET.fromstring(response.content)

    rows = []
    for item in root.findall("Item"):
        rows.append(
            {
                "currency_id": item.attrib["ID"].strip(),
                "name": item.findtext("Name", "").strip(),
                "eng_name": item.findtext("EngName", "").strip(),
                "nominal": int(item.findtext("Nominal", "1").strip()),
                "parent_code": item.findtext("ParentCode", "").strip(),
                "iso_num_code": item.findtext("ISO_Num_Code", "").strip(),
                "char_code": item.findtext("ISO_Char_Code", "").strip(),
            }
        )

    dictionary = pd.DataFrame(rows).drop_duplicates()
    dictionary.to_csv(RAW_DIR / "cbr_currency_dictionary.csv", index=False)
    return dictionary


def select_currency_meta(dictionary: pd.DataFrame, codes: Iterable[str]) -> list[CurrencyMeta]:
    selected = []
    for code in codes:
        candidates = dictionary[dictionary["char_code"].eq(code)].copy()
        if candidates.empty:
            raise ValueError(f"Currency code {code} was not found in CBR dictionary")

        # For the selected modern currencies the first current CBR record is enough.
        row = candidates.iloc[0]
        selected.append(
            CurrencyMeta(
                currency_id=str(row["currency_id"]),
                char_code=str(row["char_code"]),
                name=str(row["name"]),
                nominal=int(row["nominal"]),
            )
        )
    return selected


def load_currency_series(meta: CurrencyMeta) -> pd.DataFrame:
    params = {
        "date_req1": format_cbr_date(START_DATE),
        "date_req2": format_cbr_date(END_DATE),
        "VAL_NM_RQ": meta.currency_id,
    }
    response = fetch_url(CBR_DYNAMIC_URL, params=params)
    root = ET.fromstring(response.content)

    rows = []
    for record in root.findall("Record"):
        nominal = int(record.findtext("Nominal", str(meta.nominal)))
        value_for_nominal = parse_cbr_float(record.findtext("Value", "nan"))
        rows.append(
            {
                "date": parse_cbr_date(record.attrib["Date"]),
                "currency_id": meta.currency_id,
                "char_code": meta.char_code,
                "currency_name": meta.name,
                "nominal": nominal,
                "value_rub_per_nominal": value_for_nominal,
                "rate_rub": value_for_nominal / nominal,
            }
        )

    data = pd.DataFrame(rows)
    if data.empty:
        raise ValueError(f"CBR returned no data for {meta.char_code}")
    return data


def load_world_bank_indicator(indicator: str, output_name: str) -> pd.DataFrame:
    params = {"format": "json", "per_page": "200"}
    response = fetch_url(WORLD_BANK_URL.format(indicator=indicator), params=params)
    payload = response.json()
    records = payload[1] if isinstance(payload, list) and len(payload) > 1 else []

    rows = []
    for item in records:
        rows.append(
            {
                "year": int(item["date"]),
                "indicator_id": indicator,
                "indicator_name": item["indicator"]["value"],
                "metric": output_name,
                "value": item["value"],
                "last_updated": payload[0].get("lastupdated"),
            }
        )

    return pd.DataFrame(rows)


def load_world_bank_macro() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames = [
        load_world_bank_indicator(indicator, output_name)
        for indicator, output_name in WORLD_BANK_INDICATORS.items()
    ]
    macro_long = pd.concat(frames, ignore_index=True)
    macro_long.to_csv(RAW_DIR / "world_bank_macro_raw.csv", index=False)

    macro_wide = (
        macro_long.pivot_table(index="year", columns="metric", values="value", aggfunc="first")
        .reset_index()
        .sort_values("year")
    )
    for column in macro_wide.columns:
        if column != "year":
            macro_wide[column] = pd.to_numeric(macro_wide[column], errors="coerce")

    macro_wide.to_csv(PROCESSED_DIR / "world_bank_macro_processed.csv", index=False)
    return macro_long, macro_wide


def add_period(year: int) -> str:
    if year <= 2016:
        return "2014-2016: высокая турбулентность"
    if year <= 2019:
        return "2017-2019: относительная стабилизация"
    if year <= 2021:
        return "2020-2021: пандемийный период"
    if year <= 2023:
        return "2022-2023: новый шок и адаптация"
    return "2024-2026: свежий период"


def mark_extreme_returns(group: pd.DataFrame) -> pd.Series:
    returns = group["log_return"].dropna()
    if returns.empty or math.isclose(float(returns.std(ddof=0)), 0.0):
        return pd.Series(False, index=group.index)

    mean_value = returns.mean()
    std_value = returns.std(ddof=0)
    z_score = (group["log_return"] - mean_value) / std_value
    return z_score.abs().gt(3).fillna(False)


def build_processed_rates(raw_rates: pd.DataFrame) -> pd.DataFrame:
    data = raw_rates.copy()
    data["date"] = pd.to_datetime(data["date"])
    data = data.drop_duplicates(subset=["date", "char_code"]).sort_values(
        ["char_code", "date"]
    )

    data["year"] = data["date"].dt.year
    data["month"] = data["date"].dt.month
    data["quarter"] = data["date"].dt.quarter
    data["period"] = data["year"].map(add_period)

    grouped = data.groupby("char_code", group_keys=False)
    data["previous_rate_rub"] = grouped["rate_rub"].shift(1)
    data["rate_change_rub"] = data["rate_rub"] - data["previous_rate_rub"]
    data["daily_return_pct"] = grouped["rate_rub"].pct_change() * 100
    data["log_return"] = grouped["rate_rub"].transform(lambda x: np.log(x / x.shift(1)))
    data["days_since_previous_rate"] = grouped["date"].diff().dt.days

    data["rolling_mean_30"] = grouped["rate_rub"].transform(
        lambda x: x.rolling(30, min_periods=10).mean()
    )
    data["rolling_volatility_30"] = grouped["log_return"].transform(
        lambda x: x.rolling(30, min_periods=10).std() * np.sqrt(252) * 100
    )
    data["rate_index_2014"] = grouped["rate_rub"].transform(lambda x: x / x.iloc[0] * 100)
    data["extreme_return"] = grouped.apply(mark_extreme_returns).reset_index(
        level=0, drop=True
    )

    data.to_csv(PROCESSED_DIR / "cbr_currency_rates_processed.csv", index=False)
    return data


def build_annual_summary(processed_rates: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    annual = (
        processed_rates.groupby(["char_code", "currency_name", "year"])
        .agg(
            observations=("rate_rub", "size"),
            mean_rate_rub=("rate_rub", "mean"),
            median_rate_rub=("rate_rub", "median"),
            min_rate_rub=("rate_rub", "min"),
            max_rate_rub=("rate_rub", "max"),
            first_rate_rub=("rate_rub", "first"),
            last_rate_rub=("rate_rub", "last"),
            std_rate_rub=("rate_rub", "std"),
            mean_abs_daily_return_pct=("daily_return_pct", lambda x: x.abs().mean()),
            max_abs_daily_return_pct=("daily_return_pct", lambda x: x.abs().max()),
            annualized_volatility_pct=(
                "log_return",
                lambda x: x.dropna().std() * np.sqrt(252) * 100,
            ),
            extreme_return_days=("extreme_return", "sum"),
        )
        .reset_index()
    )
    annual["annual_return_pct"] = (
        annual["last_rate_rub"] / annual["first_rate_rub"] - 1
    ) * 100
    annual["rate_range_pct"] = (
        annual["max_rate_rub"] / annual["min_rate_rub"] - 1
    ) * 100

    annual = annual.merge(macro, on="year", how="left")
    annual.to_csv(PROCESSED_DIR / "annual_currency_summary.csv", index=False)
    return annual


def main() -> None:
    ensure_dirs()

    dictionary = load_currency_dictionary()
    selected_meta = select_currency_meta(dictionary, TARGET_CURRENCY_CODES)

    raw_rates = pd.concat(
        [load_currency_series(meta) for meta in selected_meta], ignore_index=True
    )
    raw_rates.to_csv(RAW_DIR / "cbr_currency_rates_raw.csv", index=False)

    _, macro = load_world_bank_macro()
    processed_rates = build_processed_rates(raw_rates)
    annual = build_annual_summary(processed_rates, macro)

    print("Data collection finished")
    print(f"Raw rates: {raw_rates.shape[0]} rows, {raw_rates.shape[1]} columns")
    print(f"Processed rates: {processed_rates.shape[0]} rows, {processed_rates.shape[1]} columns")
    print(f"Annual summary: {annual.shape[0]} rows, {annual.shape[1]} columns")
    print(f"Date range: {processed_rates['date'].min().date()} - {processed_rates['date'].max().date()}")


if __name__ == "__main__":
    main()
