#pragma once
#include <cstddef>
#include <cstdint>
// Buffer contract: write exactly min(input length, output capacity) bytes only
// for functions with output side effects; other functions leave output alone.
extern "C" std::uint64_t wuxiang_task(std::uint64_t x, const std::uint8_t* input,
    std::size_t length, std::uint8_t* output, std::size_t capacity);
