import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import serial


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", wintypes.WORD),
        ("wMonth", wintypes.WORD),
        ("wDayOfWeek", wintypes.WORD),
        ("wDay", wintypes.WORD),
        ("wHour", wintypes.WORD),
        ("wMinute", wintypes.WORD),
        ("wSecond", wintypes.WORD),
        ("wMilliseconds", wintypes.WORD),
    ]


def parse_nmea_rmc_utc(line: str):
    if not line.startswith("$"):
        return None
    parts = line.split(",")
    if len(parts) < 10:
        return None
    if not parts[0].lstrip("$").endswith("RMC"):
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
        for _ in range(200):
            raw = ser.readline().decode(errors="ignore").strip()
            gps_dt = parse_nmea_rmc_utc(raw)
            if gps_dt is not None:
                return gps_dt, raw
    return None, None


def set_windows_utc(dt_utc: datetime):
    st = SYSTEMTIME()
    st.wYear = dt_utc.year
    st.wMonth = dt_utc.month
    st.wDay = dt_utc.day
    st.wHour = dt_utc.hour
    st.wMinute = dt_utc.minute
    st.wSecond = dt_utc.second
    st.wMilliseconds = int(dt_utc.microsecond / 1000)
    st.wDayOfWeek = dt_utc.weekday()

    result = ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st))
    if result == 0:
        raise ctypes.WinError()


def main():
    parser = argparse.ArgumentParser(description="Set Windows UTC from GPS RMC UTC.")
    parser.add_argument("--port", required=True, help="Serial port (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Serial read timeout seconds")
    parser.add_argument("--dry-run", action="store_true", help="Show target UTC without setting system time")
    args = parser.parse_args()

    gps_dt, sentence = get_gps_utc(args.port, args.baud, args.timeout)
    if gps_dt is None:
        print("No valid RMC UTC sentence received from GPS.")
        return

    print(f"NMEA: {sentence}")
    print(f"GPS UTC to apply: {gps_dt.isoformat()}")

    if args.dry_run:
        print("Dry run enabled; system clock was not changed.")
        return

    set_windows_utc(gps_dt)
    print("Windows system UTC updated successfully.")


if __name__ == "__main__":
    main()
