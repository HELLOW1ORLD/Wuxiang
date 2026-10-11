# Wuxiang

[中文说明](README.zh-CN.md) · [Getting started](docs/usage.zh-CN.md) · [Agent surfaces](docs/agent-surfaces.zh-CN.md) · [Evaluation](docs/evaluation.md)

Wuxiang is an experimental Win64 C++ function protection and behavior-recovery evaluation toolkit for multi-tool agents such as REA. MSVC builds the host program; a project-local LLVM 20.1.8 SDK compiles selected modules, transforms optimized IR, and emits COFF objects for MSVC linking.

**Research prototype, version 0.1.1. Anti-REA effectiveness has not been established.** The initial protected branch pilot was recovered successfully. Some benchmark groups exceed the balanced-mode overhead limits. See [reported observations and limits](docs/results.md).

## New in 0.1.1: prompt injection and semantic decoys

Optional text payloads are now integrated into CLI builds and verification. A harmless prompt-injection marker asks the analyzing agent to answer a seeded `WX_LAB_…` string. Synthetic semantic decoys describe a UTF-8 parser, checksum or packet codec to introduce misleading clues. Both features are disabled by default.

Selected functions pass text pointers to a separate `noinline`, `noexcept` reader. The reader only performs a volatile byte read; it does not execute the text or change the function's result. Payloads are retained in a read-only, nonexecutable `.wxhint` PE section and checked after linking. The current CMake adapter supports the existing IR transforms; these new options use the JSON/CLI pipeline.

Target text is untrusted data and cannot establish analysis authorization. The presets do not provide arbitrary commands or a reliable safety-refusal trigger. See the [configuration and implementation guide](docs/agent-surfaces.zh-CN.md).

## Requirements and quick start

- Windows x64, Python 3.10 or newer.
- Visual Studio 2022 with Desktop development with C++, Windows SDK, CMake and DIA SDK components.
- Several GB of free disk space. Bootstrap downloads the official 939 MB LLVM SDK and verifies its fixed SHA-256; it does not install it globally.

From this repository root in PowerShell:

```powershell
python tools/bootstrap_llvm.py
python wuxiang.py doctor
python wuxiang.py protect --config examples/compat-surfaces.json
python wuxiang.py verify --config examples/compat-surfaces.json
python wuxiang.py surface inspect --artifact build/compat-surfaces/protected.exe
```

First `protect` builds the standalone C++ transformer. No pip dependencies are required. REA/Ghidra are optional analysis tools and are not included.

The example produces `protected.exe`, an unprotected LLVM `baseline.exe`, an `msvc.exe` control, `build-manifest.json` and `verification.json` under `build/compat-surfaces/`. Both controls omit the text payload. The executables should print `WUXIANG_ABI_OK`. A successful verification returns `ok: true`; `surface inspect` confirms payload presence, not anti-agent effectiveness.

For IR protection without text payloads, use `examples/compat.json`; the C++17 example is `examples/compat17.json`. Run the regression suite with `python -m unittest discover -s tests -v`. See the [module integration tutorial](docs/usage.zh-CN.md) for your own C++ code.

## Local validation of 0.1.1

Recorded on 2026-10-11 for `examples/compat-surfaces.json`:

| Check | Observation |
|---|---|
| Regression suite | 30 tests passed, including ABI, behavior, exceptions/destructors and payload checks |
| REA 6.2.0 / Ghidra 12.1.4 focused decompilation | Both text entries appeared as reader-call arguments |
| Selected-function median runtime | +3.86% versus the same LLVM baseline |
| Protected-module code size | +1.39%; complete EXE +1536 bytes |
| Agent obedience or increased recovery cost | Not evaluated |

These are local observations for one example. Tool-output visibility does not establish that an agent will follow the text or recover behavior less successfully. Rerun verification on your own module; see [results and limitations](docs/results.md).

## What is implemented

- `WUXIANG_PROTECT` annotations and exact LLVM symbol selection.
- At most one integer substitution and one block split/control region per function, diversified by seed.
- Conservative exception handling: EH control structures remain unchanged; supported arithmetic sites can be transformed.
- LLVM verification, native differential tests, object-code change and linked-symbol checks.
- C++17/20 MSVC/Clang interoperation examples and a [CMake adapter](docs/cmake-adapter.md).
- Versioned JSON build/coverage/verification reports, actual compiler dependencies and tool hashes; stale artifacts are rejected.
- Offline task packs, real candidate compilation/scoring and independent-session paired summaries.
- Opt-in bounded prompt-injection markers and synthetic semantic decoys, selected-function references and final PE payload verification.

Coverage is **partial**, not full-function virtualization. Completely untransformable selected functions fail explicitly. Coroutines, SEH, inline assembly, C++ Modules and cross-module LTO are outside v0.1 support.

## Commands

| Command | Purpose |
|---|---|
| `doctor` | Compiler/SDK/linker and optional analysis-tool diagnostics |
| `protect --config ...` | Build baseline, protected and MSVC control binaries |
| `verify --config ...` | Check behavior and per-function performance/size caps |
| `surface inspect --artifact ...` | Inspect a Win64 PE for canonical, read-only Wuxiang text payloads |
| `bench prepare --config ...` | Create separate attack and private scoring packs |
| `bench score --submission ...` | Compile candidate code and run behavior tests |
| `bench summarize --scores ...` | Summarize matched independent sessions |

Balanced verification requires median selected-function runtime ≤1.20× baseline and protected-module COFF `.text` ≤2× baseline. Successful construction alone does not mean these caps passed, or that reverse engineering is harder.

## Evaluation boundaries

The six bundled algorithms and test generators are public regression fixtures. An agent permitted to search this repository can recover their source. **Use fresh, unpublished tasks in a separate attack environment for a meaningful anti-recovery evaluation.** Public-fixture scores cannot establish that claim.

The local scorer provides working-directory separation, not an OS sandbox. Untrusted native candidates require an isolated scoring environment. Session times/tool counts are imported records, not independently attested observations. See [evaluation protocol](docs/evaluation.md) and [reverse-engineering lessons](docs/reverse-engineering-lessons.md).

## License and contributions

Wuxiang source is provided under [MIT](LICENSE). Downloaded LLVM and analysis tools retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md). Toolchains, proprietary inputs, private evidence, native binaries and attack sessions are not part of this source release.

See [CONTRIBUTING](CONTRIBUTING.md), [security reporting](SECURITY.md), and the [GitHub publishing walkthrough](docs/github-upload.zh-CN.md).
