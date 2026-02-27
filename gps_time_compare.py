import argparse
from datetime import datetime, timezone
import serial


def parse_nmea_rmc_utc(line: str):
    if not line.startswith("$"):
        return None
    parts = line.split(",")
    if len(parts) < 10:
        return None

    sentence = parts[0].lstrip("$")
    if not sentence.endswith("RMC"):
        return None

    time_raw = parts[1]
    status = parts[2]
    date_raw = parts[9]

    if status != "A" or not time_raw or not date_raw:
        return None

    try:
        hh = int(time_raw[0:2])
        mm = int(time_raw[2:4])
        ss = int(time_raw[4:6])
        frac = 0
        if "." in time_raw:
            frac_str = time_raw.split(".", 1)[1]
            frac = int((frac_str + "000000")[:6])

        day = int(date_raw[0:2])
        month = int(date_raw[2:4])
        yy = int(date_raw[4:6])
        year = 2000 + yy if yy < 80 else 1900 + yy

        return datetime(year, month, day, hh, mm, ss, frac, tzinfo=timezone.utc)
    except (ValueError, IndexError):
        return None


def get_gps_utc(port: str, baud: int, timeout: float):
    with serial.Serial(port=port, baudrate=baud, timeout=timeout) as ser:
        warned_not_valid_yet = False
        for _ in range(200):
            raw = ser.readline().decode(errors="ignore").strip()
            gps_dt = parse_nmea_rmc_utc(raw)
            if gps_dt is not None:
                return gps_dt, raw

            if raw.startswith("$"):
                parts = raw.split(",")
                if len(parts) >= 3 and parts[0].lstrip("$").endswith("RMC") and parts[2] != "A":
                    if not warned_not_valid_yet:
                        print("GPRMC not valid yet (waiting for GPS fix)...")
                        warned_not_valid_yet = True
    return None, None


def main():
    parser = argparse.ArgumentParser(description="Compare GPS UTC and Windows UTC.")
    parser.add_argument("--port", required=True, help="Serial port (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Serial read timeout seconds")
    args = parser.parse_args()

    gps_dt, sentence = get_gps_utc(args.port, args.baud, args.timeout)
    if gps_dt is None:
        print("No valid RMC UTC sentence received from GPS.")
        return

    system_dt = datetime.now(timezone.utc)
    offset_seconds = (system_dt - gps_dt).total_seconds()

    print(f"NMEA: {sentence}")
    print(f"GPS UTC    : {gps_dt.isoformat()}")
    print(f"System UTC : {system_dt.isoformat()}")
    print(f"Offset (system - gps): {offset_seconds:+.3f} s")


if __name__ == "__main__":
    main()
