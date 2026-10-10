#include "task.h"
#include "../include/wuxiang/protect.h"
#include <algorithm>
#ifndef TASK_ID
#error TASK_ID must select one of six benchmark categories
#endif
#if TASK_ID == 5
__declspec(noinline) static std::uint64_t rotate(std::uint64_t v) { return (v << 7) | (v >> 57); }
__declspec(noinline) static std::uint64_t mix(std::uint64_t v, std::uint64_t b) {
    return rotate((v ^ b) * UINT64_C(0x9E3779B185EBCA87)) ^ (v >> 11);
}
#endif
extern "C" WUXIANG_PROTECT std::uint64_t wuxiang_task(std::uint64_t x,
    const std::uint8_t* p, std::size_t n, std::uint8_t* out, std::size_t cap) {
#if TASK_ID == 0
    if (x < 17) return (x * 3) ^ 0x19;
    if (x & 1) return (x ^ 0xA53) + (x >> 3);
    return (x << 2) - 7;
#elif TASK_ID == 1
    std::uint64_t state = x & 3, total = x;
    for (std::size_t i = 0; i < n; ++i) {
        if (!p[i]) state = 0;
        else if (p[i] & 1) state = (state + 1) & 3;
        else state ^= 2;
        total = total * 33 + state * 7 + p[i];
    }
    return total ^ state;
#elif TASK_ID == 2
    if (!n) return UINT64_MAX;
    std::uint64_t value = 0;
    for (std::size_t i = 0; i < n; ++i) {
        if (p[i] < '0' || p[i] > '9') return UINT64_MAX;
        const auto digit = p[i] - '0';
        if (value > (UINT64_MAX - digit) / 10) return UINT64_MAX;
        value = value * 10 + digit;
    }
    return value;
#elif TASK_ID == 3
    static const std::uint64_t table[] = {31,7,101,53,19,233,11,89,41,157,3,67,211,29,131,17};
    std::uint64_t value = table[x & 15];
    for (std::size_t i = 0; i < n; ++i) value = value * 17 + table[(p[i] ^ x) & 15];
    return value;
#elif TASK_ID == 4
    std::uint64_t value = x;
    for (std::size_t i = 0; i < std::min(n, cap); ++i) {
        out[i] = p[i] ^ static_cast<std::uint8_t>(x + i * 17);
        value = (value << 5) ^ (value >> 2) ^ out[i];
    }
    return value;
#elif TASK_ID == 5
    std::uint64_t value = x ^ 0xC0FFEE;
    for (std::size_t i = 0; i < n; ++i) value = mix(value, p[i]);
    return mix(value, n);
#else
#error Invalid TASK_ID
#endif
}
