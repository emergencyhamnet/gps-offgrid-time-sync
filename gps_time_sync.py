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
    parser.add_argument("port", nargs="?", help="Serial port (e.g. COM3)")
    parser.add_argument("--port", dest="port_opt", help="Serial port (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Serial read timeout seconds")
    parser.add_argument("--warn", type=float, default=0.25, help="Warn if absolute offset is at least this many seconds (default: 0.25)")
    parser.add_argument("--sync-threshold", type=float, default=0.5, help="Only sync when absolute offset is at least this many seconds (default: 0.5)")
    parser.add_argument("--dry-run", action="store_true", help="Show target UTC without setting system time")
    args = parser.parse_args()

    port = args.port_opt or args.port
    if not port:
        parser.error("the following arguments are required: --port (or positional port)")

    gps_dt, sentence = get_gps_utc(port, args.baud, args.timeout)
    if gps_dt is None:
        print("No valid RMC UTC sentence received from GPS.")
        return

    system_dt = datetime.now(timezone.utc)
    offset_seconds = (system_dt - gps_dt).total_seconds()
    abs_offset = abs(offset_seconds)

    print(f"NMEA: {sentence}")
    print(f"GPS UTC to apply: {gps_dt.isoformat()}")
    print(f"System UTC now : {system_dt.isoformat()}")
    print(f"Offset (system - gps): {offset_seconds:+.3f} s")

    if abs_offset >= args.warn:
        print(f"WARNING: absolute offset {abs_offset:.3f} s exceeds warn threshold {args.warn:.3f} s")

    if args.dry_run:
        print("Dry run enabled; system clock was not changed.")
        return

    if abs_offset < args.sync_threshold:
        print(f"No sync needed (|offset| {abs_offset:.3f} s < sync threshold {args.sync_threshold:.3f} s).")
        return

    set_windows_utc(gps_dt)
    print("Windows system UTC updated successfully.")


if __name__ == "__main__":
    main()
