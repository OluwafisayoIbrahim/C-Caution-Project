
"""Static checks for a wiring.csv / parts.csv pair (Net, Component:Pin).

This is NOT a circuit simulator.  It catches wiring mistakes and known design pitfalls in the
netlist text.  The IC pinouts are hard-coded below from the standard NE555 and CD4017 pinouts
(select parts whose datasheets meet the stated electrical requirements).

    python3 tools/check_netlist.py <folder-with-parts.csv-and-wiring.csv> [--red N] [--green N]

Exit status 1 if any ERROR is reported.  WARN and INFO never fail the run.
Works on both the original blueprint package and the corrected one.
"""
import argparse
import csv
import pathlib
import re
import sys
from collections import defaultdict


NE555 = {1: "GND", 2: "TRIG", 3: "OUT", 4: "RESET", 5: "CTRL", 6: "THRES", 7: "DISCH", 8: "VCC"}
CD4017 = {1: "Q5", 2: "Q1", 3: "Q0", 4: "Q2", 5: "Q6", 6: "Q7", 7: "Q3", 8: "VSS",
          9: "Q8", 10: "Q4", 11: "Q9", 12: "CARRY", 13: "INHIBIT", 14: "CLOCK", 15: "RESET", 16: "VDD"}
CD4017_NC_OK = {12}      
SPECIAL = {"ARDUINO", "NE555", "CD4017", "SUPPLY", "U1", "U2", "U3"}  
BAD_ARDUINO_PINS = {"D0", "D1", "D13"}               

RANGE = re.compile(r"^([A-Za-z]+)(\d+)-([A-Za-z]+)(\d+)$")
VALUE = re.compile(r"(\d+(?:\.\d+)?)\s*([pnuµmkM]?)(F|f|ohm|Ω)?")
MULT = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3, "": 1.0, "k": 1e3, "M": 1e6}


def expand(ref):
    m = RANGE.match(ref)
    if not m or m.group(1) != m.group(3):
        return [ref]
    return [f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(4)) + 1)]


def parse_value(text):
    m = VALUE.search(text or "")
    if not m:
        return None
    return float(m.group(1)) * MULT[m.group(2)]


class Findings:
    def __init__(self):
        self.items = []

    def add(self, level, msg):
        self.items.append((level, msg))

    def count(self, level):
        return sum(1 for l, _ in self.items if l == level)


def load(folder):
    folder = pathlib.Path(folder)
    parts, nets, pin_nets = {}, defaultdict(list), defaultdict(list)
    with open(folder / "parts.csv", newline="") as f:
        for row in csv.DictReader(f):
            for ref in expand(row["Ref"].strip()):
                parts[ref] = row
    ties = [] 
    with open(folder / "wiring.csv", newline="") as f:
        for row in csv.DictReader(f):
            net, cp = row["Net"].strip(), row["Component:Pin"].strip()
            if ":" not in cp:
                ties.append((net, cp))
                continue
            comp, pin = cp.rsplit(":", 1)
            for ref in expand(comp):
                nets[net].append((ref, pin))
                pin_nets[(ref, pin)].append(net)
    for net, target in ties:  
        for ref, pin in nets.pop(net, []):
            nets[target].append((ref, pin))
            pin_nets[(ref, pin)] = [target]
    return parts, nets, pin_nets


def other_pin(nets, pin_nets, ref, pin_here, pins):
    """Net of the other pin of a 2-pin part."""
    for p in pins:
        if p != pin_here:
            n = pin_nets.get((ref, p))
            return n[0] if n else None
    return None


def check(folder, want_red, want_green, f):
    parts, nets, pin_nets = load(folder)
    info = {}

    
    wired = {ref for pins in nets.values() for ref, _ in pins}
    for ref in sorted(wired - set(parts) - SPECIAL):
        f.add("ERROR", f"{ref} appears in wiring.csv but not in parts.csv")
    for ref in sorted(set(parts) - wired - SPECIAL):
        f.add("ERROR", f"{ref} is listed in parts.csv but never wired")
    with open(pathlib.Path(folder) / "parts.csv", newline="") as fh:
        for row in csv.DictReader(fh):
            n = len(expand(row["Ref"].strip()))
            try:
                q = int(row["Quantity"])
            except ValueError:
                q = None
            if q is not None and q != n:
                f.add("ERROR", f"parts.csv quantity for {row['Ref']} is {q} but the ref range has {n}")

    
    for name, pins in nets.items():
        if len(pins) < 2:
            f.add("ERROR", f"net {name} has only {len(pins)} connection(s): {pins}")
    for (ref, pin), names in pin_nets.items():
        if len(set(names)) > 1:
            f.add("ERROR", f"{ref}:{pin} is in more than one net: {sorted(set(names))}")

    gnd = set(nets.get("GND", []))
    vcc = set(nets.get("+5V", []))
    if not gnd or not vcc:
        f.add("ERROR", "nets named GND and +5V are required")

    def net_of(ref, pin):
        names = pin_nets.get((ref, pin))
        return names[0] if names else None

    def same_net(a_ref, a_pin, b_ref, b_pin):
        a = net_of(a_ref, a_pin)
        return a is not None and a == net_of(b_ref, b_pin)

    def resistor_between(netname, rail_pins):
        """True if a resistor on `netname` has its other end on the rail (set of (ref, pin))."""
        for ref, pin in nets.get(netname, []):
            if ref.startswith("R") and ref in parts:
                for p in ("A", "B"):
                    if p != pin and (ref, p) in rail_pins:
                        return True
        return False

    
    for pin in NE555:
        if net_of("NE555", str(pin)) is None:
            f.add("ERROR", f"NE555 pin {pin} ({NE555[pin]}) is not connected")
    for pin in CD4017:
        if net_of("CD4017", str(pin)) is None and pin not in CD4017_NC_OK:
            f.add("ERROR", f"CD4017 pin {pin} ({CD4017[pin]}) is not connected")
    for pin, want in (("1", "GND"), ("8", "+5V")):
        if net_of("NE555", pin) != want:
            f.add("ERROR", f"NE555 pin {pin} should be on {want}")
    if net_of("CD4017", "8") != "GND" or net_of("CD4017", "16") != "+5V":
        f.add("ERROR", "CD4017 VSS (8) must be GND and VDD (16) must be +5V")
    inh_net = net_of("CD4017", "13")
    inh_members = set(nets.get(inh_net, [])) if inh_net else set()
    if inh_net != "GND" and not (inh_members & gnd):
        f.add("ERROR", "CD4017 CLOCK INHIBIT (pin 13) must be tied to GND or the counter will not count")
   
    if net_of("NE555", "2") != net_of("NE555", "6"):
        f.add("ERROR", "NE555 TRIG (2) and THRES (6) must be on the same net for astable operation")
    if not (same_net("NE555", "7", "R1", "B") and same_net("NE555", "7", "R2", "A")):
        f.add("ERROR", "NE555 DISCH (7) must be at the R1:B / R2:A junction")
    if net_of("R1", "A") != "+5V":
        f.add("ERROR", "R1:A must connect the 555 charge path to +5V")
    if not (same_net("R2", "B", "NE555", "2") and same_net("C1", "POS", "NE555", "2") and
            net_of("C1", "NEG") == "GND"):
        f.add("ERROR", "R2:B and C1:POS must join NE555 pins 2/6, with C1:NEG on GND")
    if not (same_net("NE555", "5", "C2", "POS") and net_of("C2", "NEG") == "GND"):
        f.add("ERROR", "NE555 CTRL (5) must be bypassed to GND through C2")

    
    required_links = [
        (("ARDUINO", "D2"), ("NE555", "3"), "Arduino D2 must sense NE555 OUT (3)"),
        (("CD4017", "14"), ("NE555", "3"), "CD4017 CLOCK (14) must use NE555 OUT (3)"),
        (("ARDUINO", "D8"), ("NE555", "4"), "Arduino D8 must drive NE555 RESET (4)"),
        (("ARDUINO", "D9"), ("CD4017", "15"), "Arduino D9 must drive CD4017 RESET (15)"),
        (("ARDUINO", "D10"), ("QP1", "GATE"), "Arduino D10 must drive the QP1 gate"),
    ]
    for (a_ref, a_pin), (b_ref, b_pin), message in required_links:
        if not same_net(a_ref, a_pin, b_ref, b_pin):
            f.add("ERROR", message)

    
    ctrl_pins = {"GATE", "BASE"}
    groups = {}
    for pin, label in CD4017.items():
        if not label.startswith("Q"):
            continue
        nn = net_of("CD4017", str(pin))
        members = [m for m in nets.get(nn, []) if m != ("CD4017", str(pin))] if nn else []
       
        ctrl = [m for m in members if m[1] in ctrl_pins]
        for ref, p in members:
            if ref.startswith("RBRED") and p in ("A", "B"):
                far = net_of(ref, "B" if p == "A" else "A")
                ctrl += [m for m in nets.get(far, []) if m[1] in ctrl_pins]
        if len(ctrl) != 1:
            f.add("ERROR", f"CD4017 {label} (pin {pin}) must drive exactly one switch, found {len(ctrl)}")
        else:
            groups[label] = ctrl[0][0]
            m = re.match(r"QN(\d+)$", ctrl[0][0])
            if m and int(m.group(1)) != int(label[1:]) + 1:
                f.add("ERROR", f"CD4017 {label} drives {ctrl[0][0]}; expected QN{int(label[1:]) + 1} "
                               "so the groups chase in order")
    info["outputs_wired"] = len(groups)

    
    if not resistor_between(net_of("NE555", "4"), gnd):
        f.add("ERROR", "NE555 RESET (pin 4) has no pull-down to GND: the 555 can start at power-up "
                       "while the Arduino pin is still floating")
    nobipolar = "CMOS" in ((parts.get("U2") or parts.get("NE555") or {}).get("Part", "")).upper()
    if not nobipolar and not resistor_between(net_of("NE555", "3"), vcc):
        f.add("ERROR", "NE555 output (pin 3) has no pull-up to +5V: this design requires the "
                       "documented clock-level margin measure, or a compatible CMOS-timer interface")
    if not resistor_between(net_of("CD4017", "15"), gnd):
        f.add("ERROR", "CD4017 RESET (pin 15) has no pull-down to GND: floating while the Arduino boots")

    
    red = sorted(r for r in parts if r.startswith("DRED"))
    green = sorted(r for r in parts if r.startswith("DGREEN"))
    info["red_leds"], info["green_leds"] = len(red), len(green)
    if len(red) != want_red:
        f.add("ERROR", f"design has {len(red)} red LEDs but the sign has ~{want_red}")
    if len(green) != want_green:
        f.add("ERROR", f"design has {len(green)} green LEDs but the sign has {want_green}")

    
    for led in red + green:
        an = net_of(led, "ANODE")
        res = [m for m in nets.get(an, []) if m[0].startswith("R") and m[0] in parts]
        if len(res) != 1:
            f.add("ERROR", f"{led} must have exactly one series resistor on its anode, found {len(res)}")
        ca = net_of(led, "CATHODE")
        if led.startswith("DGREEN") and ca != "GND":
            f.add("ERROR", f"{led} cathode must be on GND")

    green_pins = ["D3", "D4", "D5", "D6", "D7", "D11", "D12",
                  "A0", "A1", "A2", "A3", "A4"]
    for i, pin in enumerate(green_pins, start=1):
        if not same_net("ARDUINO", pin, f"RGREEN{i}", "A"):
            f.add("ERROR", f"green order mismatch: Arduino {pin} must drive RGREEN{i}")
        if not same_net(f"RGREEN{i}", "B", f"DGREEN{i}", "ANODE"):
            f.add("ERROR", f"RGREEN{i}:B must connect only the intended DGREEN{i} anode net")
    for i in range(1, want_red + 1):
        if not same_net(f"RRED{i}", "B", f"DRED{i}", "ANODE"):
            f.add("ERROR", f"RRED{i}:B must connect the intended DRED{i} anode net")
    
    rails = {net_of(r, "A") for r in parts if r.startswith("RRED")}
    if len(rails) > 1:
        f.add("ERROR", f"red LED resistors are not all on the same rail: {sorted(map(str, rails))}")

   
    sink_nets = {}
    for led in red:
        sink_nets.setdefault(net_of(led, "CATHODE"), []).append(led)
    per_group = []
    for name, leds in sink_nets.items():
        sw = [m for m in nets.get(name, []) if m[1] in ("DRAIN", "COLLECTOR")]
        if len(sw) != 1:
            f.add("ERROR", f"red sink net {name} must have exactly one switch, found {len(sw)}")
            continue
        per_group.append(len(leds))
        ref = sw[0][0]
        if net_of(ref, "SOURCE") != "GND" and net_of(ref, "EMITTER") != "GND" and \
           not any((ref, p) in gnd for p in ("SOURCE", "EMITTER")):
            f.add("ERROR", f"{ref} source/emitter must be on GND")
    if per_group:
        info["leds_per_group"] = sorted(set(per_group))
        if len(sink_nets) != 10:
            f.add("ERROR", f"{len(sink_nets)} red groups found; the CD4017 has exactly 10 outputs")
        if len(set(per_group)) > 1:
            f.add("WARN", f"red groups have uneven LED counts: {sorted(set(per_group))}")

    
    hs = [m for m in nets.get(next(iter(rails), ""), []) if m[1] == "DRAIN"]
    if not hs:
        f.add("WARN", "no high-side switch found on the red LED rail; one 4017 output would stay lit")
    else:
        ref = hs[0][0]
        if (ref, "SOURCE") not in vcc:
            f.add("ERROR", f"{ref} (high-side switch) source must be on +5V")
        gate_net = net_of(ref, "GATE")
        if not resistor_between(gate_net, vcc):
            f.add("ERROR", f"{ref} gate has no pull-up to +5V: the red supply could turn on at power-up")

    
    ard = [(p, n) for (r, p), n in pin_nets.items() if r == "ARDUINO" and p not in ("GND", "5V")]
    for pin, names in ard:
        if pin in BAD_ARDUINO_PINS:
            f.add("WARN", f"Arduino {pin} is used (serial pin / on-board LED); prefer another pin")
    info["arduino_pins_used"] = len(ard)

    
    decouple = 0
    for ref in parts:
        if not ref.startswith("C"):
            continue
        ends = set()
        for (r, p), names in pin_nets.items():
            if r == ref:
                ends.add(names[0])
        if {"GND", "+5V"} <= ends:
            decouple += 1
    info["supply_capacitors"] = decouple
    if decouple < 2:
        f.add("ERROR", f"need at least 2 supply decoupling capacitors (GND to +5V), found {decouple}")

  
    r1, r2, c1 = (parse_value(" ".join(filter(None, (parts.get(k, {}).get("Value"), parts.get(k, {}).get("Part")))))
                  for k in ("R1", "R2", "C1"))
    if None not in (r1, r2, c1):
        t_high = 0.693 * (r1 + r2) * c1
        t_low = 0.693 * r2 * c1
        info["555_f_hz"] = 1 / (t_high + t_low)
        info["555_period_s"] = t_high + t_low
        info["lap_s"] = 10 * (t_high + t_low)
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--red", type=int, default=50, help="expected red LED count (default 50)")
    ap.add_argument("--green", type=int, default=12, help="expected green LED count (default 12)")
    args = ap.parse_args(argv)
    f = Findings()
    info = check(args.folder, args.red, args.green, f)
    for level, msg in f.items:
        print(f"{level:5}  {msg}")
    print("\nInfo:")
    for k, v in info.items():
        print(f"  {k}: {v:.4g}" if isinstance(v, float) else f"  {k}: {v}")
    print(f"\n{f.count('ERROR')} error(s), {f.count('WARN')} warning(s)")
    return 1 if f.count("ERROR") else 0


if __name__ == "__main__":
    sys.exit(main())
