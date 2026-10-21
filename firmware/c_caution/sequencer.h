

#ifndef CCAUTION_SEQUENCER_H
#define CCAUTION_SEQUENCER_H

#include <stdint.h>

namespace ccaution {

const uint8_t kGreenCount = 12; 
const uint8_t kRedGroups = 10;   
static_assert(kGreenCount < 16u, "greenMask must fit all green LED bits");

struct Config {
  uint32_t bootMs;              
  uint32_t firstPulseTimeoutMs; 
  uint32_t clockTimeoutMs;      
  uint8_t redLaps;             
  uint32_t gapMs;              
  uint32_t greenStepMs;         
  bool greenAccumulate;        
  uint32_t gapEndMs;           
  uint32_t faultRetryMs;        
};

inline Config defaultConfig() {
  Config c = {100, 3000, 1000, 3, 300, 250, false, 500, 3000};
  return c;
}

struct Inputs {
  uint32_t nowMs;  
  bool clockHigh; 
};

struct Outputs {
  bool timerRun;      
  bool counterReset;
  bool redSupplyOn; 
  uint16_t greenMask; 
};

enum State {
  S_BOOT = 0,
  S_RED_ARM,     
  S_RED_RUN,     
  S_RED_FINISH,  
  S_GAP,        
  S_GREEN,     
  S_GAP_END,     
  S_FAULT        
};

class Sequencer {
 public:
  explicit Sequencer(const Config& cfg)
      : cfg_(cfg), state_(S_BOOT), started_(false), prevClock_(false), sawHigh_(false),
        stateStart_(0), lastEdgeMs_(0), edges_(0), cycles_(0), faults_(0), greenMask_(0) {}

  Outputs update(const Inputs& in) {
    if (!started_) {  
      started_ = true;
      stateStart_ = in.nowMs;
      lastEdgeMs_ = in.nowMs;
      prevClock_ = in.clockHigh;
    }
    const bool rising = !prevClock_ && in.clockHigh;
    const bool falling = prevClock_ && !in.clockHigh;
    prevClock_ = in.clockHigh;
    const uint32_t now = in.nowMs;
    const uint32_t elapsed = now - stateStart_;

    switch (state_) {
      case S_BOOT:
        if (elapsed >= cfg_.bootMs) enter(S_RED_ARM, now);
        break;

      case S_RED_ARM:
        if (rising) sawHigh_ = true;
        if (sawHigh_ && falling) {
          enter(S_RED_RUN, now);
        } else if (elapsed >= cfg_.firstPulseTimeoutMs) {
          fault(now);
        }
        break;

      case S_RED_RUN:
        if (rising) {
          ++edges_;
          lastEdgeMs_ = now;
          if (edges_ >= targetEdges()) {
            enter(S_RED_FINISH, now);
            break;
          }
        }
        if (now - lastEdgeMs_ >= cfg_.clockTimeoutMs) fault(now);
        break;

      case S_RED_FINISH:
        
        if (falling) {
          enter(S_GAP, now);
        } else if (elapsed >= cfg_.clockTimeoutMs) {
          fault(now);
        }
        break;

      case S_GAP:
        if (elapsed >= cfg_.gapMs) enter(S_GREEN, now);
        break;

      case S_GREEN: {
        const uint32_t step = cfg_.greenStepMs ? cfg_.greenStepMs : 1;
        const uint32_t idx = elapsed / step;
        if (idx >= kGreenCount) {
          enter(S_GAP_END, now);
        } else if (cfg_.greenAccumulate) {
          greenMask_ = static_cast<uint16_t>((UINT32_C(1) << (idx + 1u)) - UINT32_C(1));
        } else {
          greenMask_ = static_cast<uint16_t>(UINT32_C(1) << idx);
        }
        break;
      }

      case S_GAP_END:
        if (elapsed >= cfg_.gapEndMs) {
          ++cycles_;
          enter(S_RED_ARM, now);
        }
        break;

      case S_FAULT:
        if (elapsed >= cfg_.faultRetryMs) {
          ++faults_;
          enter(S_BOOT, now);
        }
        break;
    }
    return outputsFor(state_);
  }

  State state() const { return state_; }
  uint32_t cycles() const { return cycles_; }  
  uint32_t faults() const { return faults_; }  
  uint16_t edges() const { return edges_; }

 private:
  uint16_t targetEdges() const {
    return static_cast<uint16_t>(static_cast<uint16_t>(cfg_.redLaps) *
                                 static_cast<uint16_t>(kRedGroups));
  }

  void enter(State s, uint32_t now) {
    state_ = s;
    stateStart_ = now;
    lastEdgeMs_ = now;
    if (s == S_RED_ARM) sawHigh_ = false;
    if (s == S_RED_RUN) edges_ = 0;
    if (s == S_GREEN) {
      greenMask_ = UINT16_C(1);
    } else {
      greenMask_ = 0;
    }
  }

  void fault(uint32_t now) { enter(S_FAULT, now); }

  Outputs outputsFor(State s) const {
    Outputs o = {false, true, false, 0};  
    switch (s) {
      case S_RED_ARM:
        o.timerRun = true;
        break;
      case S_RED_RUN:
      case S_RED_FINISH:
        o.timerRun = true;
        o.counterReset = false;
        o.redSupplyOn = true;
        break;
      case S_GREEN:
        o.greenMask = greenMask_;
        break;
      default:
        break;
    }
    return o;
  }

  Config cfg_;
  State state_;
  bool started_;
  bool prevClock_;
  bool sawHigh_;
  uint32_t stateStart_;
  uint32_t lastEdgeMs_;
  uint16_t edges_;
  uint32_t cycles_;
  uint32_t faults_;
  uint16_t greenMask_;
};

} 

#endif 
