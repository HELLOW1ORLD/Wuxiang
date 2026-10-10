#pragma once

// The annotation is consumed from optimized LLVM IR. MSVC supplies the
// unprotected reference implementation with the same non-inlining contract.
#if defined(__clang__)
#define WUXIANG_PROTECT __attribute__((annotate("wuxiang.protect"), noinline))
#elif defined(_MSC_VER)
#define WUXIANG_PROTECT __declspec(noinline)
#else
#define WUXIANG_PROTECT __attribute__((noinline))
#endif
