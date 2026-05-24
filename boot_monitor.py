import argparse
import re
import sys
import time


CODE_SUCCESS = 0
CODE_CHECKPOINT_FAILED = -1
CODE_ERROR_DETECTED = -2

ERRORS = ("Hardware Error", "AER failed", "PCIe Bus Error")

CHECKPOINTS = [
    ("Booting Trusted Firmware", r"\bBooting Trusted Firmware\b"),
    ("DRAM FW version", r"\bDRAM FW version\s+(?P<value>\S+)"),
    ("DRAM DDR5 info", r"\bDRAM:\s+(?P<value>\S+\s+DDR5\s+\S+\s+\S+)\s+ECC\b"),
    ("DDR init time elapsed", r"\bDDR init time elapsed:\s+(?P<value>\d{2}:\d{2}:\d{2})\b"),
    ("Tianocore/EDK2 firmware version", r"\bTianocore/EDK2 firmware version\s+(?P<value>\S+)"),
    ("Booting Linux on physical CPU", r"\bBooting Linux on physical CPU\b"),
    ("Fedora Linux version", r"^\s*Fedora Linux\s+(?P<value>\d+)\b"),
    ("Kernel version", r"^\s*Kernel\s+(?P<value>\S+)"),
    ("Login prompt", r"\blogin:\s*$"),
]

CHECKPOINTS = [(label, re.compile(pattern)) for label, pattern in CHECKPOINTS]


def result(code, message, found, error=None):
    return {"code": code, "message": message, "found": found, "error": error}


def find_error(line):
    line = line.lower()
    for error in ERRORS:
        if error.lower() in line:
            return error
    return None


def monitor_lines(lines, verbose=False):
    """Read lines and check checkpoints in order."""
    found = []
    current_cp = 0

    for line_no, raw_line in enumerate(lines, start=1):
        line = raw_line.rstrip("\r\n")

        error = find_error(line)
        if error:
            if verbose:
                print(f"[ERROR] line {line_no}: {error}", flush=True)
            return result(CODE_ERROR_DETECTED, "error detected", found, error)

        if current_cp >= len(CHECKPOINTS):
            continue

        label, pattern = CHECKPOINTS[current_cp]
        match = pattern.search(line)
        if not match:
            continue

        value = match.groupdict().get("value")
        found.append({"label": label, "line": line_no, "value": value})
        if verbose:
            value_text = f" [{value}]" if value else ""
            print(f"[OK] CP{current_cp + 1}: {label}{value_text} (line {line_no})", flush=True)

        current_cp += 1
        if current_cp == len(CHECKPOINTS):
            return result(CODE_SUCCESS, "all checkpoints found in order", found)

    missing_label = CHECKPOINTS[current_cp][0]
    if verbose:
        print(f"[FAIL] missing CP{current_cp + 1}: {missing_label}", flush=True)
    return result(
        CODE_CHECKPOINT_FAILED,
        f"missing checkpoint CP{current_cp + 1}: {missing_label}",
        found,
    )


def monitor_realtime(lines, verbose=False):
    return monitor_lines(lines, verbose=verbose)


def follow_file(path, timeout=None, poll_interval=0.2):
    """Yield lines from a file while it is still being written."""
    deadline = time.monotonic() + timeout if timeout is not None else None
    position = 0

    while True:
        with open(path, "r", encoding="utf-8", errors="replace") as log:
            log.seek(position)
            yield from log
            position = log.tell()

        if deadline is not None and time.monotonic() >= deadline:
            return

        time.sleep(poll_interval)


def print_summary(data):
    print("BOOT MONITOR SUMMARY")
    print("  " + "=" * 60)

    for index, (label, _) in enumerate(CHECKPOINTS, start=1):
        if index <= len(data["found"]):
            item = data["found"][index - 1]
            value = f"  [{item['value']}]" if item["value"] else ""
            print(f"    [OK] CP{index}: {label}{value}  (line {item['line']})")
        else:
            print(f"    [--] CP{index}: {label}")

    if data["error"]:
        print("  " + "-" * 60)
        print(f"    ERROR: {data['error']}")
    elif data["code"] == CODE_CHECKPOINT_FAILED:
        print("  " + "-" * 60)
        print(f"    REASON: {data['message']}")

    print("  " + "-" * 60)
    print(f"    FINAL CODE: {data['code']}")


def parse_args():
    parser = argparse.ArgumentParser(description="Monitor boot checkpoints.")
    parser.add_argument("log_file", nargs="?", default="os_bootup.log")
    parser.add_argument("--timeout", type=float, help="Monitor the log in real time.")
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        if args.timeout is None:
            with open(args.log_file, "r", encoding="utf-8", errors="replace") as log:
                data = monitor_lines(log)
        else:
            data = monitor_realtime(follow_file(args.log_file, timeout=args.timeout), verbose=True)
    except OSError as exc:
        data = result(CODE_CHECKPOINT_FAILED, f"cannot read input: {exc}", [])

    print_summary(data)
    return data["code"]


if __name__ == "__main__":
    sys.exit(main())