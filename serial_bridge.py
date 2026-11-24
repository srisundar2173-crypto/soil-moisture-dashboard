from datetime import datetime
from pathlib import Path
import time
import serial

PORT = "COM5"  # Update to match the Arduino's port
BAUD = 9600
THRESHOLD = 45
CSV_PATH = Path("data/soil_readings.csv")


def main():
    print(f"Listening on {PORT} ({BAUD} baud)...")
    with serial.Serial(PORT, BAUD, timeout=2) as ser:
        time.sleep(2)
        while True:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            # Supports either "62" or "62,495" or "2026-11-24T15:10:00,62,Moist,495"
            parts = [p.strip() for p in line.split(",")]
            try:
                if len(parts) >= 2 and parts[0].isdigit():
                    pct = int(parts[0])
                    raw_adc = parts[1]
                    ts = datetime.now().isoformat(timespec="seconds")
                elif len(parts) >= 2:
                    ts = parts[0]
                    pct = int(float(parts[1]))
                    raw_adc = parts[3] if len(parts) >= 4 else ""
                else:
                    pct = int(float(parts[0]))
                    raw_adc = ""
                    ts = datetime.now().isoformat(timespec="seconds")
            except ValueError:
                continue

            pct = max(0, min(100, pct))
            status = "Moist" if pct >= THRESHOLD else "Dry"

            with CSV_PATH.open("a", encoding="utf-8") as f:
                f.write(f"{ts},{pct},{status},{raw_adc}\n")

            print(f"Logged -> {ts} | {pct}% | {status}")


if __name__ == "__main__":
    main()