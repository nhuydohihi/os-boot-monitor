# Boot Monitor

`boot_monitor.py` monitors a boot log and reports whether the boot process passes, fails, or stops because an error message appears.

The program checks that all required boot checkpoints appear in the correct order. If any configured error appears at any time, monitoring stops immediately.

## Result Codes

- `CODE 0`: all checkpoints were found in order.
- `CODE -1`: one or more checkpoints were missing or out of order.
- `CODE -2`: an error message was detected.

Error messages:

- `Hardware Error`
- `AER failed`
- `PCIe Bus Error`

The script prints the final code in the summary. The operating system may wrap
negative process exit codes, so the printed `FINAL CODE` is the value to check.

## Required Checkpoints

The checkpoints must appear in this order:

1. `Booting Trusted Firmware`
2. `DRAM FW version <dram_version>`
3. `DRAM: <ddr_capacity> DDR5 <ddr_speed> <ddr_ecc> ECC`
4. `DDR init time elapsed: <time>`
5. `Tianocore/EDK2 firmware version <firmware_version>`
6. `Booting Linux on physical CPU`
7. `Fedora Linux <linux_version>`
8. `Kernel <kernel_version>`
9. `login:`

## Usage

Use the default log file, `os_bootup.log`:

```bash
python boot_monitor.py
```

Use a specific log file:

```bash
python boot_monitor.py bootup.log
```

Monitor a log file in real time for up to 20 seconds:

```bash
python boot_monitor.py --timeout 20 live_boot.log
```

## Output Example

```text
BOOT MONITOR SUMMARY
  ============================================================
    [OK] CP1: Booting Trusted Firmware  (line 1)
    [OK] CP2: DRAM FW version  [230830-20ebfacc]  (line 8)
    [OK] CP3: DRAM DDR5 info  [768GB DDR5 5600 SYMBOL_64_16]  (line 742)
    [OK] CP4: DDR init time elapsed  [00:03:56]  (line 743)
    [OK] CP5: Tianocore/EDK2 firmware version  [05.04.00005001]  (line 1241)
    [OK] CP6: Booting Linux on physical CPU  (line 1707)
    [OK] CP7: Fedora Linux version  [41]  (line 6943)
    [OK] CP8: Kernel version  [6.12.1-ftk-ac04-64K-rel3+]  (line 6944)
    [OK] CP9: Login prompt  (line 6946)
  ------------------------------------------------------------
    FINAL CODE: 0
```
