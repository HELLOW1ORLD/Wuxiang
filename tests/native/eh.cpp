#include "wuxiang/protect.h"
#include <cstdint>
#include <stdexcept>

static volatile int destructions;
struct Guard {
  ~Guard() { destructions = destructions + 1; }
};
static __declspec(noinline) void may_throw(unsigned value) {
  if (value == 99) throw std::runtime_error("expected");
}
WUXIANG_PROTECT unsigned guarded(unsigned value) {
  Guard guard;
  may_throw(value);
  return value ^ 0x731429U;
}
int main() {
  for (unsigned value = 0; value < 256; ++value) {
    int before = destructions;
    try {
      unsigned actual = guarded(value);
      if (value == 99 || actual != (value ^ 0x731429U)) return 1;
    } catch (const std::runtime_error &) {
      if (value != 99) return 2;
    }
    if (destructions != before + 1) return 3;
  }
  return 0;
}
