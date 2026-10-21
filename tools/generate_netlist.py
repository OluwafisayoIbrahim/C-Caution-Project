
"""Generate parts.csv and wiring.csv for the documented 2021 C-Caution project.

The netlist has 62 LEDs and ~200 connections, so it is generated rather than typed by hand.
Change the numbers below, re-run, then run tools/check_netlist.py.

LED counts (~50 red, 12 green) are from my own count of the original sign and are approximate;
change RED_GROUPS * RED_PER_GROUP if the real number differs.
"""
import csv
import pathlib

RED_GROUPS = 10          
RED_PER_GROUP = 5       
GREEN_PINS = ["D3", "D4", "D5", "D6", "D7", "D11", "D12", "A0", "A1", "A2", "A3", "A4"]


Q_PINS = [3, 2, 4, 7, 10, 1, 5, 6, 9, 11]

ROOT = pathlib.Path(__file__).resolve().parent.parent


def wiring_rows():
    rows = []

    def net(name, *pins):
        for pin in pins:
            rows.append((name, pin))

    n_red = RED_GROUPS * RED_PER_GROUP
    n_green = len(GREEN_PINS)

    
    gnd = ["ARDUINO:GND", "NE555:1", "CD4017:8", "CD4017:13", 
           "C1:NEG", "C2:NEG", "C3:NEG", "C4:NEG", "C5:NEG", "RPD555:B", "RPDRST:B"]
    gnd += [f"QN{g + 1}:SOURCE" for g in range(RED_GROUPS)]
    gnd += [f"DGREEN{i + 1}:CATHODE" for i in range(n_green)]
    net("GND", *gnd)
    net("+5V", "ARDUINO:5V", "NE555:8", "CD4017:16", "R1:A", "QP1:SOURCE", "RPG:A", "RPU555:A",
        "C3:POS", "C4:POS", "C5:POS")

   
    net("555_DISCH", "NE555:7", "R1:B", "R2:A")
    net("555_TIMING", "NE555:2", "NE555:6", "R2:B", "C1:POS")
    net("555_CTRL", "NE555:5", "C2:POS")
    net("555_ENABLE", "ARDUINO:D8", "NE555:4", "RPD555:A")
    net("CLOCK", "NE555:3", "CD4017:14", "ARDUINO:D2", "RPU555:B")

    
    net("4017_RESET", "ARDUINO:D9", "CD4017:15", "RPDRST:A")

   
    net("RED_EN_N", "ARDUINO:D10", "QP1:GATE", "RPG:B")
    red_v = ["QP1:DRAIN"] + [f"RRED{k}:A" for k in range(1, n_red + 1)]
    net("RED_V+", *red_v)

    for g in range(RED_GROUPS):
        net(f"Q{g}_SIGNAL", f"CD4017:{Q_PINS[g]}", f"QN{g + 1}:GATE")
        members = [k for k in range(1, n_red + 1) if (k - 1) % RED_GROUPS == g]
        net(f"RED_SINK_{g + 1}", f"QN{g + 1}:DRAIN", *[f"DRED{k}:CATHODE" for k in members])
    for k in range(1, n_red + 1):
        net(f"RED_ANODE_{k}", f"RRED{k}:B", f"DRED{k}:ANODE")

    
    for i, pin in enumerate(GREEN_PINS, start=1):
        net(f"GREEN_DRIVE_{i}", f"ARDUINO:{pin}", f"RGREEN{i}:A")
        net(f"GREEN_ANODE_{i}", f"RGREEN{i}:B", f"DGREEN{i}:ANODE")
    return rows


def parts_rows():
    n_red = RED_GROUPS * RED_PER_GROUP
    n_green = len(GREEN_PINS)
    return [
        ("U1", "Arduino Uno / ATmega328P", "", 1, "Wired as ARDUINO. Simulator or real board"),
        ("U2", "NE555 (bipolar)", "", 1, "Wired as NE555. Astable oscillator; see notes for the CMOS alternative"),
        ("U3", "CD4017", "", 1, "Wired as CD4017. Decade counter, Q0..Q9"),
        (f"QN1-QN{RED_GROUPS}", "N-channel logic-level MOSFET", "2N7000 or equivalent", RED_GROUPS,
         f"One per red group; sinks {RED_PER_GROUP} LEDs; gate driven directly by CD4017 Qn"),
        ("QP1", "P-channel logic-level MOSFET", "", 1,
         "High-side red supply switch; pick a part with Rds(on) specified at Vgs = -4.5 V"),
        (f"DRED1-DRED{n_red}", "Red LED", "", n_red, f"{RED_GROUPS} groups x {RED_PER_GROUP}; interleaved around the triangle"),
        (f"DGREEN1-DGREEN{n_green}", "Green LED", "", n_green, "Letter C, top to bottom"),
        ("R1", "Resistor", "4.7k", 1, "555 RA"),
        ("R2", "Resistor", "10k", 1, "555 RB"),
        ("C1", "Capacitor", "10uF", 1, "555 timing capacitor (non-polarised or low-leakage preferred)"),
        ("C2", "Capacitor", "10nF", 1, "555 control pin (pin 5)"),
        ("C3-C4", "Capacitor", "100nF", 2, "Decoupling at NE555 and CD4017 supply pins"),
        ("C5", "Capacitor", "100uF", 1, "Bulk capacitor across the 5 V rail"),
        (f"RRED1-RRED{n_red}", "Resistor", "330", n_red, "One series resistor PER red LED"),
        (f"RGREEN1-RGREEN{n_green}", "Resistor", "330", n_green, "One series resistor per green LED"),
        ("RPU555", "Resistor", "4.7k", 1, "Pull-up on 555 output (pin 3) for conservative CD4017 clock-level margin"),
        ("RPD555", "Resistor", "10k", 1, "Pull-down on 555 RESET (pin 4): 555 stays off until the Arduino enables it"),
        ("RPDRST", "Resistor", "100k", 1, "Pull-down on CD4017 RESET (pin 15) while the Arduino boots"),
        ("RPG", "Resistor", "100k", 1, "Pull-up on QP1 gate: red supply stays off until the Arduino drives D10 low"),
        ("SUPPLY", "Regulated 5V supply", "", 1, "USB or regulated 5 V; see docs/DESIGN_NOTES.md for the current budget"),
    ]


def main():
    with open(ROOT / "wiring.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Net", "Component:Pin"])
        w.writerows(wiring_rows())
    with open(ROOT / "parts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Ref", "Part", "Value", "Quantity", "Details"])
        w.writerows(parts_rows())
    print(f"wrote {ROOT / 'wiring.csv'} and {ROOT / 'parts.csv'}")


if __name__ == "__main__":
    main()
