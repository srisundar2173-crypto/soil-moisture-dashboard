from datetime import datetime
import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Smart Soil Monitor", page_icon="🌿", layout="wide")

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
CSV_PATH = DATA_DIR / "soil_readings.csv"
CONTROL_PATH = DATA_DIR / "controls_state.json"

PLANT_PRESETS = {
    "General Houseplant": 45,
    "Succulent / Cactus": 25,
    "Herb / Leafy Plant": 55,
    "Custom": None,
}


def load_controls() -> dict:
    default_state = {
        "plant_type": "General Houseplant",
        "moisture_threshold": 45,
        "auto_irrigate_enabled": False,
        "manual_water_pulse": False,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if not CONTROL_PATH.exists():
        CONTROL_PATH.write_text(json.dumps(default_state, indent=2), encoding="utf-8")
        return default_state
    try:
        return {**default_state, **json.loads(CONTROL_PATH.read_text(encoding="utf-8"))}
    except json.JSONDecodeError:
        return default_state


def save_controls(state: dict) -> None:
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    CONTROL_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def ensure_sample_data() -> None:
    if not CSV_PATH.exists():
        sample_rows = [
            ["2026-11-22T09:00:00", 58, "Moist", 480],
            ["2026-11-22T15:00:00", 46, "Moist", 560],
            ["2026-11-22T21:00:00", 34, "Dry", 650],
            ["2026-11-23T09:00:00", 68, "Moist", 410],
            ["2026-11-23T15:00:00", 52, "Moist", 520],
            ["2026-11-23T21:00:00", 39, "Dry", 615],
            ["2026-11-24T09:00:00", 44, "Dry", 580],
            ["2026-11-24T15:00:00", 61, "Moist", 460],
        ]
        df = pd.DataFrame(sample_rows, columns=["timestamp", "moisture_pct", "is_moist", "raw_adc"])
        df.to_csv(CSV_PATH, index=False)


def load_readings() -> pd.DataFrame:
    ensure_sample_data()
    df = pd.read_csv(CSV_PATH)
    if df.empty:
        return pd.DataFrame(columns=["timestamp", "date", "moisture_pct", "is_moist", "raw_adc"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["moisture_pct"] = pd.to_numeric(df["moisture_pct"], errors="coerce")
    df = df.dropna(subset=["timestamp", "moisture_pct"]).sort_values("timestamp")
    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    return df


def generate_analytic_report(df: pd.DataFrame, threshold: int, scope_label: str) -> dict:
    latest = df.iloc[-1]
    latest_pct = float(latest["moisture_pct"])
    avg_pct = round(float(df["moisture_pct"].mean()), 1)
    min_pct = round(float(df["moisture_pct"].min()), 1)
    max_pct = round(float(df["moisture_pct"].max()), 1)
    moist_pct_share = round(float((df["moisture_pct"] >= threshold).mean() * 100), 1)

    # Trend across recent readings
    if len(df) >= 2:
        delta = float(df.iloc[-1]["moisture_pct"]) - float(df.iloc[-2]["moisture_pct"])
        if delta > 4:
            trend = f"Rising (+{delta:.0f}% since last reading) — moisture is increasing."
        elif delta < -4:
            trend = f"Falling ({delta:.0f}% since last reading) — soil is drying out."
        else:
            trend = "Relatively steady compared to the previous reading."
    else:
        trend = "Only one reading available so far."

    if latest_pct < max(15, threshold - 20):
        status_label = "Critically Dry"
        needs = "Water the plant soon and check that water penetrates evenly into the root zone rather than running off dry soil."
    elif latest_pct < threshold:
        status_label = "Dry (Needs Moisture)"
        needs = f"Moisture is below your {threshold}% target. Plan a light-to-moderate watering and re-check the trend."
    elif latest_pct <= 85:
        status_label = "Moist & Balanced"
        needs = "Soil moisture is in a healthy range. No immediate watering needed; keep monitoring daily swings."
    else:
        status_label = "Over-Saturated"
        needs = "Soil is very wet. Hold off on watering and verify pot drainage holes so roots don't stay waterlogged."

    summary = (
        f"For **{scope_label}**, average moisture is **{avg_pct}%** (range: **{min_pct}%–{max_pct}%**), "
        f"and the soil met or exceeded the **{threshold}%** moist threshold **{moist_pct_share}%** of the time. {trend}"
    )

    return {
        "latest_pct": round(latest_pct, 1),
        "status_label": status_label,
        "summary": summary,
        "needs": needs,
    }


controls = load_controls()
df = load_readings()

st.title("🌿 Soil Moisture Analytics & Control Portal")
st.caption("Software team dashboard for daily moisture tracking, soil health reporting, and system controls")

# --- Sidebar Controls ---
st.sidebar.header("Website Controls")

plant_choice = st.sidebar.selectbox(
    "Plant Preset",
    options=list(PLANT_PRESETS.keys()),
    index=list(PLANT_PRESETS.keys()).index(controls["plant_type"])
    if controls["plant_type"] in PLANT_PRESETS
    else 0,
)

default_thresh = PLANT_PRESETS[plant_choice] if PLANT_PRESETS[plant_choice] is not None else controls["moisture_threshold"]
threshold = st.sidebar.slider("Moist Threshold (%)", min_value=10, max_value=90, value=int(default_thresh))

auto_irrigate = st.sidebar.toggle("Auto-Watering Mode (Hardware Signal)", value=bool(controls["auto_irrigate_enabled"]))

if st.sidebar.button("Trigger Watering Pulse Now"):
    controls["manual_water_pulse"] = True
    st.sidebar.success("Water pulse flag set in controls_state.json for hardware bridge.")

if st.sidebar.button("Save Control Settings"):
    controls["plant_type"] = plant_choice
    controls["moisture_threshold"] = threshold
    controls["auto_irrigate_enabled"] = auto_irrigate
    save_controls(controls)
    st.sidebar.success("Saved control settings!")

# Persist threshold/preset/toggle changes smoothly
if (
    controls["plant_type"] != plant_choice
    or controls["moisture_threshold"] != threshold
    or controls["auto_irrigate_enabled"] != auto_irrigate
):
    controls["plant_type"] = plant_choice
    controls["moisture_threshold"] = threshold
    controls["auto_irrigate_enabled"] = auto_irrigate
    save_controls(controls)

st.sidebar.divider()
st.sidebar.subheader("Simulate / Input Reading")
sim_pct = st.sidebar.number_input("Moisture %", min_value=0, max_value=100, value=55)
if st.sidebar.button("Add Reading to Dataset"):
    now_str = datetime.now().isoformat(timespec="seconds")
    moist_flag = "Moist" if sim_pct >= threshold else "Dry"
    new_row = pd.DataFrame([[now_str, sim_pct, moist_flag, ""]], columns=["timestamp", "moisture_pct", "is_moist", "raw_adc"])
    new_row.to_csv(CSV_PATH, mode="a", header=False, index=False)
    st.rerun()

# --- Daily Filter ---
dates_desc = sorted(df["date"].unique(), reverse=True)
selected_scope = st.selectbox("View Mode / Day Filter", options=["All Days"] + dates_desc)
view_df = df if selected_scope == "All Days" else df[df["date"] == selected_scope]

report = generate_analytic_report(view_df, threshold, selected_scope)

# --- Top Metrics ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest Moisture", f"{report['latest_pct']}%")
c2.metric("Moist vs. Dry", "Moist" if report["latest_pct"] >= threshold else "Dry")
c3.metric("Condition", report["status_label"])
c4.metric("Active Threshold", f"{threshold}%")

# --- Analytic Report ---
st.subheader("Soil Analytic Report")
st.info(f"**What the soil is going through:** {report['summary']}")
st.success(f"**What the soil needs:** {report['needs']}")

# --- Graphs ---
st.subheader("Moisture Over Time")
st.line_chart(view_df.set_index("timestamp")[["moisture_pct"]], height=300)

st.subheader("Daily-Wise Moisture Summary")
daily_df = (
    df.groupby("date", as_index=False)
    .agg(
        avg_moisture=("moisture_pct", "mean"),
        min_moisture=("moisture_pct", "min"),
        max_moisture=("moisture_pct", "max"),
        samples=("moisture_pct", "count"),
    )
    .sort_values("date", ascending=False)
)
daily_df["avg_moisture"] = daily_df["avg_moisture"].round(1)
daily_df["min_moisture"] = daily_df["min_moisture"].round(1)
daily_df["max_moisture"] = daily_df["max_moisture"].round(1)

st.bar_chart(daily_df.set_index("date")["avg_moisture"], height=260)
st.dataframe(daily_df, use_container_width=True)

with st.expander("Raw Sensor Readings Log"):
    st.dataframe(view_df.sort_values("timestamp", ascending=False), use_container_width=True)