# Recreating the circuit in Proteus

## 1. Build the schematic

1. New project → schematic capture.
2. Place the parts from `parts.csv`. Wire them using `wiring.csv` (each row is `Net, Component:Pin`). Rows sharing a net name are on the same wire.
3. Shortcut for the red LEDs: build **one group** (one 4017 output → `QN1` gate; `QN1` drain → 5 LEDs, each with its own 330 Ω to the red rail), then copy/paste it 10 times and attach each copy to the next output. Output order matters: Q0 → QN1, Q1 → QN2, … Q9 → QN10.
4. Pin numbers: NE555 1 GND, 2 TRIG, 3 OUT, 4 RESET, 5 CTRL, 6 THRES, 7 DISCH, 8 VCC. CD4017: Q0 = 3, Q1 = 2, Q2 = 4, Q3 = 7, Q4 = 10, Q5 = 1, Q6 = 5, Q7 = 6, Q8 = 9, Q9 = 11, CLK = 14, RESET = 15, INHIBIT = 13 (tie to GND), VDD = 16, VSS = 8. Check against the Proteus symbols, which may differ in layout.
5. Arduino pins: D2 clock sense, D8 555 enable, D9 4017 reset, D10 red supply (active low), greens on D3, D4, D5, D6, D7, D11, D12, A0, A1, A2, A3, A4 (top of the C first).

## 2. Load the firmware

Compile `firmware/c_caution/c_caution.ino` in the Arduino IDE (Sketch → Export compiled binary), then load the `.hex` into the ATmega328P/Arduino model.

## 3. Checklist (tick off while the simulation runs)

- [ ] On start, the red LEDs stay off for a fraction of a second.
- [ ] D2 shows about 5–6 pulses per second after the red stage starts.
- [ ] Group 1 (Q0) lights first; then groups 2, 3 … 10 in order; then it repeats for 3 laps in total.
- [ ] After the third lap ends on Q0, all red LEDs go off together.
- [ ] After a short pause the green LEDs light one at a time from the top of the C to the bottom, about 4 steps per second.
- [ ] The green LEDs go off, then the red chase begins again.
- [ ] Red and green are never on together.
- [ ] Optional fault test: hold the 555 RESET pin low (or disconnect D2's signal); the outputs should all go off, then retry after about 3 s.

Write what you actually observed. If something differs (for example a Proteus model that behaves
differently from the datasheet), note it in `docs/DESIGN_NOTES.md` rather than adjusting the claim.
