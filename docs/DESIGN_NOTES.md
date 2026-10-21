# Design notes for the C-Caution project

The C-Caution sign was built as an undergraduate project in 2021 and uploaded to this repository.
These notes describe its circuit architecture, calculated timing, estimated current,
firmware behaviour, and supporting datasheet values.

## Block diagram

See `../block_diagram.svg`. Signal flow: the Arduino enables the NE555 (D8) and holds/releases
the CD4017 reset (D9). The 555 clocks the 4017 and the Arduino (D2). Each 4017 output switches
one N-MOSFET that sinks 5 red LEDs. A P-MOSFET (D10, active low) powers the red rail. The 12
green LEDs hang directly off 12 Arduino pins.

## Calculated timing

555 astable, R1 = 4.7 kΩ, R2 = 10 kΩ, C1 = 10 µF:

- t_high = 0.693 × (R1 + R2) × C1 = 0.693 × 14.7 kΩ × 10 µF ≈ 0.102 s
- t_low = 0.693 × R2 × C1 = 0.693 × 10 kΩ × 10 µF ≈ 0.069 s
- period ≈ 0.171 s, frequency ≈ 5.84 Hz (formula f = 1.44 / ((R1 + 2·R2)·C1))
- one lap of 10 groups ≈ 1.71 s; 3 laps ≈ 5.1 s
- first pulse after enabling is longer (the capacitor starts empty): about 1.0986 × (R1 + R2) × C1 ≈ 0.16 s

Full repeating cycle ≈ 0.161 s arm + 5.135 s red + 0.300 s gap + 3.000 s green
(12 × 250 ms) + 0.500 s gap = 9.096 s. The one-time boot delay adds 0.100 s before the first cycle.
Real 555 timing varies with the tolerances of the selected resistor and capacitor parts.

The formula values above are calculated, not simulated measurements. The host model rounds them
to 102 ms high, 69 ms low, and 161 ms for the first high pulse.

## Current budget (estimates)

Assumptions: red LED forward voltage about 2.0 V, green about 2.1 V (check your LEDs), 330 Ω resistors.

- Red LED estimate: (5 − 2.0 − 0.2) / 330 ≈ 8.5 mA, or about 42 mA for five
  branches. The [onsemi 2N7000 datasheet](https://www.onsemi.com/pdf/datasheet/nds7002a-d.pdf)
  specifies a maximum 0.4 V drain-source drop at Vgs = 4.5 V and Id = 75 mA at 25 °C;
  actual LED forward voltage and the chosen transistor determine the real current.
- Green LED estimate: (5 − 2.1) / 330 ≈ 8.8 mA per pin. In accumulate mode all 12
  total about 106 mA. The [Microchip ATmega328P datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/Atmel-7810-Automotive-Microcontrollers-ATmega328P_Datasheet.pdf)
  lists 40 mA per pin and 200 mA through Vcc/GND as absolute maxima, characterizes output
  voltage at 20 mA per pin at 5 V, and gives grouped-port limits. With this pin assignment the
  estimated source-current groups are about 62 mA and 44 mA, below its listed 150 mA source
  group limits. These are design checks, not measurements.
- Red and green stages do not overlap in the firmware. Estimated peak LED current is about
  42 mA red or 106 mA green in accumulate mode, plus the board and logic load.
- The [TI CD4017B datasheet](https://www.ti.com/lit/ds/symlink/cd4017b.pdf) specifies
  about 0.36 mA guaranteed source current at VDD = 5 V while holding VOH = 4.6 V at 125 °C
  (about 1 mA typical at 25 °C). That supports using MOSFET gates rather than BJT base current
  to switch a roughly 42 mA LED group.

## Clock-level and counter behaviour checked in datasheets

- The [TI NE555 datasheet](https://www.ti.com/lit/ds/symlink/ne555.pdf) specifies 2.75 V
  minimum and 3.3 V typical high output at VCC = 5 V only for IOH = −100 mA. It does not justify
  describing 3.3 V as the lightly loaded output level.
- The TI CD4017B datasheet specifies VIH = 3.5 V minimum at VDD = 5 V, advances on a positive
  clock transition when inhibit is low, and clears asynchronously to count zero when RESET is
  high. The repository includes a 4.7 kΩ pull-up at the clock interface; confirm the resulting
  high level with the selected parts during circuit testing.
- Because reset is held high for the complete first 555 pulse and released only after firmware
  observes its falling edge, the next rising edge advances Q0 to Q1. The low interval is about
  69 ms nominal, leaving ample setup time in the behavioural model.

## Why a high-side switch for the red LEDs

A CD4017 always has exactly one output high. When the red stage ends, one group would stay lit.
The P-MOSFET removes power from the whole red rail instead. Its gate is pulled up to 5 V, so it is
off until the Arduino drives D10 low. Choose a part whose Rds(on) is specified at Vgs = −4.5 V;
at 42 mA a 5 Ω on-resistance would produce a calculated drop of about 0.2 V.

The direct gate drive is valid only when the Arduino and red rail share the same regulated 5 V:
D10 HIGH then makes Vgs approximately 0 V (off), and D10 LOW makes Vgs approximately −5 V (on).
The P-MOSFET is not specified in this repository, so its Vgs rating and Rds(on) at −4.5 V remain
selection checks.

Each of the five parallel red LED branches has its own 330 Ω resistor, so the branches do not
share one current-limiting resistor. The shared N-MOSFET drain carries their combined current.

## Red LED grouping

LED k (numbered around the triangle) is on output (k − 1) mod 10, so neighbouring LEDs are on
different outputs and the pattern repeats every 10 LEDs (a "marching dots" look). This is the
physical order defined by `wiring.csv`.

## Assembly checks

1. **Choose exact transistors.** The onsemi 2N7000 values above were checked, but substitute
   N-MOSFETs and the still-unspecified P-MOSFET require Vgs, Rds(on), current, and package checks.
2. **Green order:** `GREEN_PINS` is listed from the top of the C around the arc to the bottom;
   wire the LEDs in that order.
3. **Proteus models:** select an Arduino/ATmega328P model, a CD4017, and MOSFET models matching
   the parts used in the schematic.
4. **Clock integrity:** a pulse shorter than an Arduino polling interval can clock the CD4017
   without being counted by the controller. The host test demonstrates this in the behavioural model.
