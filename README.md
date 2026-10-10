# Wuxiang

[中文说明](README.zh-CN.md) · [Getting started](docs/usage.zh-CN.md) · [Evaluation](docs/evaluation.md)

Wuxiang is an experimental Win64 C++ function protection and behavior-recovery evaluation toolkit for multi-tool agents such as REA. MSVC builds the host program; a project-local LLVM 20.1.8 SDK compiles selected modules, transforms optimized IR, and emits COFF objects for MSVC linking.

**Research prototype, version 0.1.0. Anti-REA effectiveness has not been established.** The initial protected branch pilot was recovered successfully. Some benchmark groups exceed the balanced-mode overhead limits. See [reported observations and limits](docs/results.md).

## Requirements and quick start

- Windows x64, Python 3.10 or newer.
- Visual Studio 2022 with Desktop development with C++, Windows SDK, CMake and DIA SDK components.
- Several GB of free disk space. Bootstrap downloads the official 939 MB LLVM SDK and verifies its fixed SHA-256; it does not install it globally.

From this repository root in PowerShell:

```powershell
python tools/bootstrap_llvm.py
python wuxiang.py doctor
python wuxiang.py protect --config examples/compat.json
python wuxiang.py verify --config examples/compat.json
python wuxiang.py protect --config examples/compat17.json
python wuxiang.py verify --config examples/compat17.json
python -m unittest discover -s tests -v
```

First `protect` builds the standalone C++ transformer. No pip dependencies are required. REA/Ghidra are optional analysis tools and are not included.

## What is implemented

- `WUXIANG_PROTECT` annotations and exact LLVM symbol selection.
- At most one integer substitution and one block split/control region per function, diversified by seed.
- Conservative exception handling: EH control structures remain unchanged; supported arithmetic sites can be transformed.
- LLVM verification, native differential tests, object-code change and linked-symbol checks.
- C++17/20 MSVC/Clang interoperation examples and a [CMake adapter](docs/cmake-adapter.md).
- Versioned JSON build/coverage/verification reports, actual compiler dependencies and tool hashes; stale artifacts are rejected.
- Offline task packs, real candidate compilation/scoring and independent-session paired summaries.

Coverage is **partial**, not full-function virtualization. Completely untransformable selected functions fail explicitly. Coroutines, SEH, inline assembly, C++ Modules and cross-module LTO are outside v0.1 support.

## Commands

| Command | Purpose |
|---|---|
| `doctor` | Compiler/SDK/linker and optional analysis-tool diagnostics |
| `protect --config ...` | Build baseline, protected and MSVC control binaries |
| `verify --config ...` | Check behavior and per-function performance/size caps |
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
