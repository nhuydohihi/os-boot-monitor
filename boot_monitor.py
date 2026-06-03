import argparse
import re 
import sys
import time

BOOT_PASSED = 0
BOOT_FAILED_MISSING_CHECKPOINT = -1
BOOT_FAILED_ERROR_DETECTED = -2

ERROR_DETECTOR = re.compile(
    r"Hardware Error|AER failed|PCIe Bus Error", re.IGNORECASE
)

CHECKPOINTS = [
    ("Booting Trusted Firmware", re.compile(r"\bBooting Trusted Firmware\b")),
    ("DRAM FW version", re.compile(r"\bDRAM FW version\s+(?P<value>\S+)")),
    ("DRAM DDR5 info", re.compile(r"\bDRAM:\s+(?P<value>\S+\s+DDR5\s+\S+\s+\S+)\s+ECC\b")),
    ("DDR init time elapsed", re.compile(r"\bDDR init time elapsed:\s+(?P<value>\d{2}:\d{2}:\d{2})\b")),
    ("Tianocore/EDK2 firmware version", re.compile(r"\bTianocore/EDK2 firmware version\s+(?P<value>\S+)")),
    ("Booting Linux on physical CPU", re.compile(r"\bBooting Linux on physical CPU\b")),
    ("Fedora Linux version", re.compile(r"^\s*Fedora Linux\s+(?P<value>\d+)\b")),
    ("Kernel version", re.compile(r"^\s*Kernel\s+(?P<value>\S+)")),
    ("Login prompt", re.compile(r"\blogin:\s*$")),
] 

# Report 
def generate_report(status_code, status_message, captured_checkpoints, critical_error=None):
    return {
        "code": status_code,
        "message": status_message,
        "found": captured_checkpoints,
        "error": critical_error,
    }

# Monitor 
def start_monitoring(line_stream, verbose=False):

    captured_checkpoints = []
    next_checkpoint_idx = 0
    total_checkpoints = len(CHECKPOINTS)

    for line_no, raw_line in enumerate(line_stream, start=1):
        line = raw_line.rstrip("\r\n")

        # 1. System Errors Check 
        error_match = ERROR_DETECTOR.search(line)
        if error_match:
            detected_error = error_match.group(0) 
            if verbose: 
                print(f"[CRITICAL ERROR] Line {line_no}: Found '{detected_error}'. Stopping monitor immediately.", flush=True)
                # Print and Return right after detecting critical error
            return generate_report(
                BOOT_FAILED_ERROR_DETECTED, "Critical hardware error detected", captured_checkpoints, detected_error
            )
        if next_checkpoint_idx >= total_checkpoints:
            continue

        # 2. Check current checkpoint in order 
        label, pattern = CHECKPOINTS[next_checkpoint_idx]
        match = pattern.search(line)
        if not match:
            continue

        value = match.groupdict().get("value")
        captured_checkpoints.append({"label": label, "line": line_no, "value": value})

        if verbose:
            value_text = f" [{value}]" if value else ""
            print(f"[MATCH OK] CP{next_checkpoint_idx + 1}/{total_checkpoints}: {label}{value_text} (Line {line_no})", flush=True)

        next_checkpoint_idx += 1
        
        if next_checkpoint_idx == total_checkpoints:
            return generate_report(BOOT_PASSED, "All checkpoints found in correct order", captured_checkpoints)

    # End of file reached but not all checkpoints found 
    missing_label = CHECKPOINTS[next_checkpoint_idx][0]

    if verbose:
        print(f"[BOOT FAILED] Missing checkpoint {next_checkpoint_idx + 1}: '{missing_label}'", flush=True)
        
    return generate_report(
        BOOT_FAILED_MISSING_CHECKPOINT,
        f"Boot sequence interrupted. Missing: {missing_label}",
        captured_checkpoints,
    )

def tail_file(file_path, timeout=None, poll_interval=0.2):
    deadline = time.monotonic() + timeout if timeout is not None else None

    with open(file_path, "r", encoding="utf-8", errors="replace") as log_file:
        while True:
            for line in log_file:
                yield line
            if deadline is not None and time.monotonic() >= deadline:
                break
            time.sleep(poll_interval)

def print_final_summary(report):
    """In bảng tổng hợp kết quả trực quan ra console."""
    print("\n" + "=" * 60)
    print("                      BOOT MONITOR SUMMARY")
    print("=" * 60)

    for index, (label, _) in enumerate(CHECKPOINTS, start=1):

        if index <= len(report["found"]):
            item = report["found"][index - 1]
            value = f" -> [{item['value']}]" if item["value"] else ""
            print(f"  [OK]  CP{index}: {label:<35} (Line {item['line']}){value}")
        else:
            print(f"  [--]  CP{index}: {label:<35} (NOT FOUND)")

    print("-" * 60)
    if report["error"]:
        print(f"  CRITICAL ERROR STOP: {report['error']}")
    elif report["code"] == BOOT_FAILED_MISSING_CHECKPOINT:
        print(f"  FAIL REASON: {report['message']}")
        
    print(f"  FINAL SYSTEM CODE: {report['code']}")
    print("=" * 60)


def parse_arguments():
    parser = argparse.ArgumentParser(description="Real-time OS Bootup Monitor CLI Tool.")
    parser.add_argument("log_file", nargs="?", default="OS_bootup.log")
    parser.add_argument("--timeout", type=float, help="Set execution time limit in seconds for real-time monitoring.")
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    try:
        if args.timeout is None:
            with open(args.log_file, "r", encoding="utf-8", errors="replace") as file:
                report = start_monitoring(file, verbose=False)
    
        else:
            print(f"[INFO] Starting real-time monitor on '{args.log_file}' with {args.timeout}s timeout...")
            log_stream = tail_file(args.log_file, timeout=args.timeout)
            report = start_monitoring(log_stream, verbose=True)
            
    except OSError as err:
        report = generate_report(BOOT_FAILED_MISSING_CHECKPOINT, f"File System Error: {err}", [])

    print_final_summary(report)
    return report["code"]

sys.exit(main()) 