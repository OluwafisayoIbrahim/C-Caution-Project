# Repository changes

The C-Caution sign was an undergraduate project carried out in 2021 and uploaded to this
repository. This file records the changes and safeguards included in the uploaded project.

## Implemented safeguards

- **First counter step:** `S_RED_ARM` holds the CD4017 reset active through the modelled first
  555 pulse and releases it after the falling edge. The host test then observes Q0 first.
- **Fault handling:** a missing first pulse, a stuck-high clock, or a clock that stops during the
  chase moves the controller to `S_FAULT`, switches outputs off, and retries after the configured delay.
- **Safe output setup:** the sketch writes each safe output level before changing the pin to output mode.
- **Safe output transitions:** the sketch switches the red rail off before changing the counter or
  timer state, and switches it on only after the counter and timer outputs are ready.
- **AVR-width arithmetic:** green masks use explicitly sized integer constants, and the red-edge
  target is calculated within the range of `uint16_t` for the 8-bit lap setting.
- **Generated wiring:** `tools/generate_netlist.py` produces both CSV files. The checker validates
  the Arduino pin map, 555 topology, CD4017 order, pull resistors, LED resistors, and MOSFET sources.
- **Clock-glitch coverage:** the behavioural test shows that a pulse shorter than the polling
  interval can advance its counter model without being counted by the controller.

## Current design decisions

| Area | Repository implementation | Basis |
|---|---|---|
| Red LEDs | 50 LEDs in ten groups of five | Fixed by the generated parts and wiring files |
| Green LEDs | 12 individually driven LEDs | Fixed by the firmware pin array and wiring file |
| Red group drivers | Ten N-channel MOSFETs | Keeps CD4017 outputs from carrying LED-group current |
| Red supply | P-channel MOSFET driven by D10, active low | Turns the complete red rail off between stages |
| Timing | NE555 astable using 4.7 kΩ, 10 kΩ, and 10 µF | Produces a calculated nominal rate of 5.84 Hz |
| Firmware | Non-blocking state machine | Supports host testing and rollover-safe elapsed-time arithmetic |

## Verification recorded in the repository

- The firmware test program contains 35 checks for timing calculations, sequence order, lap
  settings, green modes, faults, repeat cycles, glitches, and `millis()` rollover.
- The netlist regression program contains 18 checks, including eight deliberately broken wiring cases.
- Official datasheet links and calculation assumptions are recorded in `docs/DESIGN_NOTES.md`.
