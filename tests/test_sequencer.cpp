
#include <cmath>
#include <cstdio>
#include <vector>

#include "../firmware/c_caution/sequencer.h"

using namespace ccaution;

static int g_checks = 0, g_failed = 0;
#define CHECK(cond, msg)                                              \
  do {                                                                \
    ++g_checks;                                                       \
    if (!(cond)) {                                                    \
      ++g_failed;                                                     \
      std::printf("  FAIL  %s  [%s:%d]\n", msg, __FILE__, __LINE__);  \
    }                                                                 \
  } while (0)


static const double R1 = 4700.0, R2 = 10000.0, C1 = 10e-6;
static const int T_HIGH = (int)std::lround(0.693 * (R1 + R2) * C1 * 1000.0);       
static const int T_LOW = (int)std::lround(0.693 * R2 * C1 * 1000.0);                
static const int T_FIRST = (int)std::lround(1.0986 * (R1 + R2) * C1 * 1000.0);    

struct Rig {
  explicit Rig(int highMs = T_HIGH, int lowMs = T_LOW, int firstMs = T_FIRST)
      : tHigh(highMs), tLow(lowMs), tFirst(firstMs) {}


  bool en = false, out = false;
  int remaining = 0;
  bool deadLow = false;    
  bool stuckHigh = false;  
  int tHigh, tLow, tFirst;
  
  int count = 0;
  bool prevOut = false;
  
  Outputs o = {false, true, false, 0};

  void step() {
    
    if (!o.timerRun) {
      en = false;
      out = false;
    } else if (!en) {
      en = true;
      out = true;  
      remaining = tFirst;
    } else if (--remaining == 0) {
      out = !out;
      remaining = out ? tHigh : tLow;
    }
    bool pin = out;
    if (deadLow) pin = false;
    if (stuckHigh) pin = true;
    
    if (o.counterReset) {
      count = 0;
    } else if (!prevOut && pin) {
      count = (count + 1) % kRedGroups;
    }
    prevOut = pin;
    clock = pin;
  }
  bool clock = false;
  bool glitchInjected = false;

  
  void injectRisingGlitch() {
    if (clock) return;
    clock = true;
    if (!prevOut && !o.counterReset) count = (count + 1) % kRedGroups;
    prevOut = true;
    glitchInjected = true;
  }

  int litGroup() const { return o.redSupplyOn ? count : -1; }
};

struct Sample {
  uint32_t t;
  int group;
  uint16_t green;
  State st;
  uint32_t cycle;
  Outputs o;
};


static std::vector<Sample> run(Sequencer& seq, Rig& rig, uint32_t t0, uint32_t ms,
                               bool (*hook)(Sequencer&, Rig&, uint32_t) = nullptr) {
  std::vector<Sample> log;
  for (uint32_t i = 0; i < ms; ++i) {
    rig.step();
    if (hook && hook(seq, rig, i)) {}
    rig.o = seq.update(Inputs{t0 + i, rig.clock});
    log.push_back(Sample{t0 + i, rig.litGroup(), rig.o.greenMask, seq.state(), seq.cycles(), rig.o});
  }
  return log;
}


static std::vector<int> redSequence(const std::vector<Sample>& log, uint32_t cycle) {
  std::vector<int> seq;
  int last = -2;
  for (const Sample& s : log) {
    if (s.cycle != cycle) continue;
    if (s.group < 0) {
      last = -2;
      continue;
    }
    if (s.group != last) seq.push_back(s.group);
    last = s.group;
  }
  return seq;
}

static std::vector<uint16_t> greenSequence(const std::vector<Sample>& log, uint32_t cycle) {
  std::vector<uint16_t> seq;
  uint16_t last = 0;
  for (const Sample& s : log) {
    if (s.cycle != cycle) continue;
    if (s.green != 0 && s.green != last) seq.push_back(s.green);
    last = s.green;
  }
  return seq;
}

static std::vector<int> expectedRed(int laps) {
  std::vector<int> v;
  for (int lap = 0; lap < laps; ++lap)
    for (int g = 0; g < kRedGroups; ++g) v.push_back(g);
  v.push_back(0);  
  return v;
}

static uint32_t firstStateTime(const std::vector<Sample>& log, State state) {
  for (const Sample& s : log)
    if (s.st == state) return s.t;
  return UINT32_MAX;
}

static void testModelTimingFormulae() {
  std::printf("555 model timing matches the documented formulae\n");
  CHECK(T_HIGH == 102, "0.693 * (R1 + R2) * C1 should round to 102 ms");
  CHECK(T_LOW == 69, "0.693 * R2 * C1 should round to 69 ms");
  CHECK(T_FIRST == 161, "1.0986 * (R1 + R2) * C1 should round to 161 ms");
}

static void testBootIsSafe() {
  std::printf("boot is safe\n");
  Sequencer seq(defaultConfig());
  Outputs o = seq.update(Inputs{1000, false});
  CHECK(!o.timerRun && o.counterReset && !o.redSupplyOn && o.greenMask == 0,
        "first update must be all-off with the counter held in reset");
}

static void testRedSequenceStartsAtQ0AndRunsInOrder() {
  std::printf("red stage: starts at Q0, order Q0..Q9 x laps, ends at Q0\n");
  Sequencer seq(defaultConfig());
  Rig rig;
  std::vector<Sample> log = run(seq, rig, 0, 12000);
  std::vector<int> got = redSequence(log, 0);
  std::vector<int> want = expectedRed(defaultConfig().redLaps);
  CHECK(got == want, "red group sequence differs from Q0..Q9 repeated, then Q0");
  CHECK(!got.empty() && got.front() == 0, "first lit group must be Q0 (blueprint started at Q1)");
}

static void testRedStageEndsSafely() {
  std::printf("red stage: everything off at the end\n");
  Sequencer seq(defaultConfig());
  Rig rig;
  std::vector<Sample> log = run(seq, rig, 0, 12000);
  bool sawGap = false;
  for (const Sample& s : log) {
    if (s.st == S_GAP) {
      sawGap = true;
      CHECK(!s.o.timerRun && s.o.counterReset && !s.o.redSupplyOn && s.o.greenMask == 0,
            "GAP must switch the timer and red supply off and hold the counter in reset");
      break;
    }
  }
  CHECK(sawGap, "never reached the gap after the red stage");
}

static void testGreenSweepOrderAndTiming() {
  std::printf("green stage: top-to-bottom, one LED at a time, 250 ms steps, never with red\n");
  Sequencer seq(defaultConfig());
  Rig rig;
  std::vector<Sample> log = run(seq, rig, 0, 14000);
  std::vector<uint16_t> got = greenSequence(log, 0);
  std::vector<uint16_t> want;
  for (int i = 0; i < kGreenCount; ++i) want.push_back((uint16_t)(1u << i));
  CHECK(got == want, "green masks must be bit0, bit1 ... bit11 in order");


  int run_len = 0;
  uint16_t last = 0;
  bool durationsOk = true;
  for (const Sample& s : log) {
    if (s.cycle != 0) continue;
    if (s.green == last && s.green != 0) {
      ++run_len;
    } else {
      if (last != 0 && std::abs(run_len - 250) > 1) durationsOk = false;
      run_len = (s.green != 0) ? 1 : 0;
    }
    last = s.green;
  }
  CHECK(durationsOk, "each green step should last 250 ms (+/-1 ms)");

  bool overlap = false;
  for (const Sample& s : log)
    if (s.green != 0 && s.o.redSupplyOn) overlap = true;
  CHECK(!overlap, "red and green must never be on together");
}

static void testCycleRepeats() {
  std::printf("cycle repeats and the 2nd red stage matches the 1st\n");
  Sequencer seq(defaultConfig());
  Rig rig;
  std::vector<Sample> log = run(seq, rig, 0, 26000);
  CHECK(seq.cycles() == 2, "expected exactly two completed cycles in 26 s");
  CHECK(redSequence(log, 0) == redSequence(log, 1), "2nd cycle red sequence differs from 1st");
  CHECK(greenSequence(log, 0) == greenSequence(log, 1), "2nd cycle green sequence differs from 1st");
}

static void testMillisRollover() {
  std::printf("millis() rollover during the green timed state does not change behaviour\n");
  Sequencer a(defaultConfig()), b(defaultConfig());
  Rig ra, rb;
  std::vector<Sample> base = run(a, ra, 0, 12000);

  std::vector<Sample> wrap = run(b, rb, UINT32_MAX - 6000u, 12000);
  CHECK(redSequence(base, 0) == redSequence(wrap, 0), "red sequence changed across rollover");
  CHECK(greenSequence(base, 0) == greenSequence(wrap, 0), "green sequence changed across rollover");
}

static void testGreenAccumulate() {
  std::printf("green accumulate mode fills bit0 through bit11\n");
  Config cfg = defaultConfig();
  cfg.greenAccumulate = true;
  Sequencer seq(cfg);
  Rig rig;
  std::vector<uint16_t> got = greenSequence(run(seq, rig, 0, 12000), 0);
  std::vector<uint16_t> want;
  for (uint8_t i = 0; i < kGreenCount; ++i)
    want.push_back(static_cast<uint16_t>((UINT32_C(1) << (i + 1u)) - UINT32_C(1)));
  CHECK(got == want, "accumulate masks must fill from bit0 through bit11");
}

static void testRedLapCounts() {
  std::printf("redLaps = 1 and 5 produce the requested edge sequences\n");
  for (uint8_t laps : {uint8_t(1), uint8_t(5)}) {
    Config cfg = defaultConfig();
    cfg.redLaps = laps;
    Sequencer seq(cfg);
    Rig rig;
    const uint32_t duration = laps == 1 ? 6000u : 15000u;
    std::vector<Sample> log = run(seq, rig, 0, duration);
    CHECK(redSequence(log, 0) == expectedRed(laps), "red sequence did not match redLaps");
  }
}

static void testSlowerClockWithMatchingTimeout() {
  std::printf("slower 2 Hz clock runs when the timeout is configured to match\n");
  Config cfg = defaultConfig();
  cfg.redLaps = 1;
  cfg.firstPulseTimeoutMs = 700;
  cfg.clockTimeoutMs = 600;
  Sequencer seq(cfg);
  Rig rig(300, 200, 500); 
  std::vector<Sample> log = run(seq, rig, 0, 10000);
  CHECK(redSequence(log, 0) == expectedRed(1), "slower clock red sequence was incorrect");
  CHECK(seq.faults() == 0 && seq.state() != S_FAULT, "matching timeout must not fault at 2 Hz");
}

static bool injectClockGlitch(Sequencer& seq, Rig& rig, uint32_t) {
  if (!rig.glitchInjected && seq.state() == S_RED_RUN && seq.edges() == 5 && !rig.clock)
    rig.injectRisingGlitch();
  return false;
}

static void testSubPollClockGlitchCanDesynchronize() {
  std::printf("a sub-poll clock glitch can advance the counter without being counted\n");
  Config cfg = defaultConfig();
  cfg.redLaps = 1;
  Sequencer normal(cfg), glitched(cfg);
  Rig normalRig, glitchRig;
  std::vector<Sample> base = run(normal, normalRig, 0, 5000);
  std::vector<Sample> changed = run(glitched, glitchRig, 0, 5000, injectClockGlitch);
  CHECK(glitchRig.glitchInjected, "test failed to inject its short pulse");
  CHECK(redSequence(changed, 0) != expectedRed(1),
        "a pulse hidden between polls should demonstrate counter/controller desynchronization");
  CHECK(firstStateTime(changed, S_GAP) == firstStateTime(base, S_GAP),
        "an unobserved glitch should not change the controller's edge-counted stage length");
  CHECK(glitched.faults() == 0, "the level-polling controller cannot diagnose a missed short pulse");
}

static void testZeroGreenStepIsGuarded() {
  std::printf("greenStepMs = 0 is clamped to 1 ms and does not divide by zero\n");
  Config cfg = defaultConfig();
  cfg.redLaps = 1;
  cfg.greenStepMs = 0;
  Sequencer seq(cfg);
  Rig rig;
  std::vector<uint16_t> got = greenSequence(run(seq, rig, 0, 6000), 0);
  CHECK(got.size() == kGreenCount, "zero greenStepMs should still emit all 12 steps");
  CHECK(seq.cycles() >= 1, "zero greenStepMs should still complete the cycle");
}

static void testFaultNoClock() {
  std::printf("fault: clock never starts\n");
  Sequencer seq(defaultConfig());
  Rig rig;
  rig.deadLow = true;
  std::vector<Sample> log = run(seq, rig, 0, 4500);
  bool faulted = false;
  for (const Sample& s : log) {
    if (s.st == S_FAULT) {
      faulted = true;
      CHECK(!s.o.timerRun && s.o.counterReset && !s.o.redSupplyOn && s.o.greenMask == 0,
            "FAULT must be all-off");
      break;
    }
  }
  CHECK(faulted, "controller never reported a fault with a dead clock");
}

static void testFaultClockStuckHigh() {
  std::printf("fault: clock stuck high\n");
  Sequencer seq(defaultConfig());
  Rig rig;
  rig.stuckHigh = true;
  std::vector<Sample> log = run(seq, rig, 0, 4500);
  bool faulted = false;
  for (const Sample& s : log) faulted = faulted || s.st == S_FAULT;
  CHECK(faulted, "stuck-high clock should be a fault, not an endless wait");
}

static bool killClockMidRun(Sequencer& seq, Rig& rig, uint32_t) {
  if (seq.state() == S_RED_RUN && seq.edges() >= 5) rig.deadLow = true;
  return false;
}

static void testFaultClockStopsMidRun() {
  std::printf("fault: clock dies mid-chase, then recovers on retry\n");
  Sequencer seq(defaultConfig());
  Rig rig;
  std::vector<Sample> log = run(seq, rig, 0, 3000, killClockMidRun);
  bool faulted = false;
  for (const Sample& s : log) faulted = faulted || s.st == S_FAULT;
  CHECK(faulted, "a clock that stops mid-chase must trigger a fault");
  CHECK(!rig.o.redSupplyOn, "red supply must be off after the fault");
  
  rig.deadLow = false;
  std::vector<Sample> after = run(seq, rig, 3000, 12000);
  CHECK(seq.faults() == 1, "exactly one completed fault retry should have been counted");
  bool ranRed = false;
  for (const Sample& s : after) ranRed = ranRed || s.group >= 0;
  CHECK(ranRed, "after the clock is repaired the red chase should run again");
}

static void testBlueprintSkippedQ0() {
  std::printf("documenting the blueprint flaw: releasing the 555 with the counter free skips Q0\n");
  Rig rig;
  rig.o = Outputs{true, false, true, 0};
  int first = -1;
  for (int i = 0; i < 400 && first < 0; ++i) {
    rig.step();
    if (rig.litGroup() >= 0 && rig.count != 0) first = rig.count;
    if (rig.litGroup() == 0 && i > 0) break;
  }
  CHECK(first == 1, "model should show the counter jumping to Q1 on the first pulse");
}

int main() {
  std::printf("555 timing used by the rig: high %d ms, low %d ms, first pulse %d ms (period %d ms)\n",
              T_HIGH, T_LOW, T_FIRST, T_HIGH + T_LOW);
  testModelTimingFormulae();
  testBootIsSafe();
  testRedSequenceStartsAtQ0AndRunsInOrder();
  testRedStageEndsSafely();
  testGreenSweepOrderAndTiming();
  testCycleRepeats();
  testMillisRollover();
  testGreenAccumulate();
  testRedLapCounts();
  testSlowerClockWithMatchingTimeout();
  testSubPollClockGlitchCanDesynchronize();
  testZeroGreenStepIsGuarded();
  testFaultNoClock();
  testFaultClockStuckHigh();
  testFaultClockStopsMidRun();
  testBlueprintSkippedQ0();
  std::printf("\n%d checks, %d failed\n", g_checks, g_failed);
  return g_failed ? 1 : 0;
}
