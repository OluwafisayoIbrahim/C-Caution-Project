#if defined(__INTELLISENSE__) && !defined(ARDUINO)
#include <stdint.h>

constexpr uint8_t LOW = 0;
constexpr uint8_t HIGH = 1;
constexpr uint8_t INPUT = 0;
constexpr uint8_t OUTPUT = 1;
constexpr uint8_t A0 = 14;
constexpr uint8_t A1 = 15;
constexpr uint8_t A2 = 16;
constexpr uint8_t A3 = 17;
constexpr uint8_t A4 = 18;

void digitalWrite(uint8_t pin, uint8_t value);
void pinMode(uint8_t pin, uint8_t mode);
int digitalRead(uint8_t pin);
unsigned long millis();
#endif

#include "sequencer.h"

using namespace ccaution;

constexpr uint8_t PIN_CLOCK_SENSE = 2;
constexpr uint8_t PIN_TIMER_ENABLE = 8;
constexpr uint8_t PIN_COUNTER_RESET = 9;
constexpr uint8_t PIN_RED_SUPPLY_N = 10;
constexpr uint8_t GREEN_PINS[] = {3, 4, 5, 6, 7, 11, 12, A0, A1, A2, A3, A4};

static_assert(sizeof(GREEN_PINS) / sizeof(GREEN_PINS[0]) == kGreenCount,
              "GREEN_PINS must contain one pin for each green LED");

Sequencer sequencer(defaultConfig());

static void applyOutputs(const Outputs& o) {
  if (!o.redSupplyOn) {
    digitalWrite(PIN_RED_SUPPLY_N, HIGH);
  }

  digitalWrite(PIN_COUNTER_RESET, o.counterReset ? HIGH : LOW);
  digitalWrite(PIN_TIMER_ENABLE, o.timerRun ? HIGH : LOW);

  for (uint8_t i = 0; i < kGreenCount; ++i) {
    digitalWrite(GREEN_PINS[i], ((o.greenMask >> i) & 1u) ? HIGH : LOW);
  }


  if (o.redSupplyOn) {
    digitalWrite(PIN_RED_SUPPLY_N, LOW);
  }
}

void setup() {
  digitalWrite(PIN_TIMER_ENABLE, LOW);
  digitalWrite(PIN_COUNTER_RESET, HIGH);
  digitalWrite(PIN_RED_SUPPLY_N, HIGH);

  pinMode(PIN_TIMER_ENABLE, OUTPUT);
  pinMode(PIN_COUNTER_RESET, OUTPUT);
  pinMode(PIN_RED_SUPPLY_N, OUTPUT);

  for (uint8_t i = 0; i < kGreenCount; ++i) {
    digitalWrite(GREEN_PINS[i], LOW);
    pinMode(GREEN_PINS[i], OUTPUT);
  }

  pinMode(PIN_CLOCK_SENSE, INPUT);
}

void loop() {
  Inputs in = {millis(), digitalRead(PIN_CLOCK_SENSE) == HIGH};
  applyOutputs(sequencer.update(in));
}
