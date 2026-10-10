#include "task.h"
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#ifndef TASK_ID
#define TASK_ID -1
#endif
static bool decode(const std::string& s, std::vector<std::uint8_t>& out) {
    if (s == "-") return true;
    if (s.size() % 2) return false;
    for (std::size_t i = 0; i < s.size(); i += 2) {
        unsigned n = 0;
        std::istringstream f(s.substr(i, 2)); f >> std::hex >> n;
        if (!f || !f.eof() || n > 255) return false;
        out.push_back(static_cast<std::uint8_t>(n));
    }
    return true;
}
int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--timing") {
        std::uint8_t input[32], output[32];
        for (unsigned i = 0; i < 32; ++i) input[i] = static_cast<std::uint8_t>('0' + i % 10);
        volatile std::uint64_t sink = 0;
        for (unsigned i = 0; i < 10000; ++i) sink = sink ^ wuxiang_task(i, input, 32, output, 32);
        std::vector<double> samples;
        for (unsigned run = 0; run < 11; ++run) {
            auto start = std::chrono::steady_clock::now();
            for (unsigned i = 0; i < 200000; ++i) sink = sink ^ wuxiang_task(i, input, 32, output, 32);
            auto end = std::chrono::steady_clock::now();
            samples.push_back(std::chrono::duration<double, std::nano>(end - start).count() / 200000);
        }
        std::sort(samples.begin(), samples.end());
        std::cout << "{\"median_ns_per_call\":" << samples[5] << ",\"repeats\":11,\"calls_per_repeat\":200000,\"sink\":" << sink << "}\n";
        return 0;
    }
    std::uint64_t x;
    std::string hex;
    std::size_t capacity;
    while (std::cin >> x >> hex >> capacity) {
        if (capacity > 1048576 || hex.size() > 2097152) return 2;
        std::vector<std::uint8_t> input;
        if (!decode(hex, input)) return 2;
        // Canary is tested for unwritten tails as well as algorithm output.
        std::vector<std::uint8_t> output(capacity, 0xCD);
        const auto value = wuxiang_task(x, input.data(), input.size(), output.data(), capacity);
        std::cout << std::dec << value << ' ';
        // Common protocol reports the entire buffer. Scorer expected cases retain
        // 0xCD in unwritten bytes, catching unintended memory side effects.
        if (output.empty()) std::cout << '-';
        else for (auto b : output) std::cout << std::hex << std::setw(2) << std::setfill('0') << unsigned(b);
        std::cout << std::dec << '\n';
    }
    return std::cin.eof() ? 0 : 2;
}
