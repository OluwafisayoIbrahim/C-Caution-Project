"""Regression tests for the static netlist checker, including deliberate breakage."""

import csv
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import check_netlist


checks = 0
failed = 0
work = ROOT / "build" / "netlist_tests"


def check(condition, message):
    global checks, failed
    checks += 1
    if not condition:
        failed += 1
        print("  FAIL ", message)


def load_rows():
    with (ROOT / "wiring.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def run_case(name, mutate=None):
    case = work / name
    case.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "parts.csv", case / "parts.csv")
    rows = load_rows()
    if mutate:
        mutate(rows)
    with (case / "wiring.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["Net", "Component:Pin"])
        writer.writeheader()
        writer.writerows(rows)
    findings = check_netlist.Findings()
    check_netlist.check(case, 50, 12, findings)
    return findings


def remove_member(member):
    def mutate(rows):
        rows[:] = [row for row in rows if row["Component:Pin"] != member]
    return mutate


def swap_members(first, second):
    def mutate(rows):
        for row in rows:
            if row["Component:Pin"] == first:
                row["Component:Pin"] = second
            elif row["Component:Pin"] == second:
                row["Component:Pin"] = first
    return mutate


def expect_failure(name, mutate, text):
    findings = run_case(name, mutate)
    errors = [message for level, message in findings.items if level == "ERROR"]
    check(bool(errors), f"{name} should fail")
    check(any(text in message for message in errors),
          f"{name} did not report the expected rule: {text}")


if work.exists():
    shutil.rmtree(work)

print("netlist checker: corrected design")
base = run_case("base")
check(base.count("ERROR") == 0, "corrected netlist should have no errors")
check(base.count("WARN") == 0, "corrected netlist should have no warnings")

print("netlist checker: deliberate mutations")
expect_failure("swap_q0_q1", swap_members("QN1:GATE", "QN2:GATE"), "expected QN")
expect_failure("delete_reset_pulldown", remove_member("RPDRST:B"), "no pull-down")
expect_failure("drop_led_resistor", remove_member("RRED1:B"), "DRED1 must have exactly one")
expect_failure("unground_source", remove_member("QN1:SOURCE"), "source/emitter must be on GND")
expect_failure("swap_d8_d9", swap_members("ARDUINO:D8", "ARDUINO:D9"), "D8 must drive NE555 RESET")
expect_failure("swap_555_ctrl_discharge", swap_members("NE555:5", "NE555:7"),
               "NE555 DISCH (7)")
expect_failure("swap_green_order", swap_members("ARDUINO:D3", "ARDUINO:D4"),
               "green order mismatch")
expect_failure("swap_red_and_green_enable", swap_members("ARDUINO:D10", "ARDUINO:D11"),
               "D10 must drive the QP1 gate")

shutil.rmtree(work)
print(f"\n{checks} checks, {failed} failed")
sys.exit(1 if failed else 0)
