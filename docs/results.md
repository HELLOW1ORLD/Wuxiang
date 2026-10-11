# Reported observations and acceptance limits

## 0.1.1 agent-surface engineering checks (2026-10-11)

The opt-in `examples/compat-surfaces.json` build passed 30 local tests, including actual COFF relocation retention, PE payload inspection, MSVC/Clang behavior and ABI checks, and exceptions/destructors with surface references. One local verification run measured selected-function runtime at 1.0386× baseline, protected-module code at 1.0139× baseline, and the complete executable at +1536 bytes. Both balanced caps passed. These are local samples, not portable overhead guarantees.

The final executable contained a 374-byte read-only payload with one marker prompt and one synthetic UTF-8 description. No agent recovery sessions were conducted against this version. Prompt following, semantic mistakes and increased recovery cost remain unmeasured. See the [implemented feature guide](agent-surfaces.zh-CN.md).

A local REA 6.2.0 / Ghidra 12.1.4 focused decompilation displayed both text entries as arguments to the separate reader calls in the selected function. This establishes tool-output visibility for this one artifact/provider, not agent obedience or increased recovery cost. Direct unused byte reads had been omitted by the decompiler; the delivered build uses separate noinline readers instead.

## Earlier 0.1.0 observations

This source release exposes implementation, tests and synthetic fixtures. Private machine-specific reports, attack sessions and the original shipped-artifact recovery evidence are excluded. The figures below summarize the developer's local observations dated 2026-10-10; this repository alone does not independently attest the original pilot or reproduce its elapsed times.

| Check | Reported observation |
|---|---|
| Local tests before source packaging | 21 tests passed |
| Synthetic native differential cases | 6,777 / 6,777 agreed across 54 binaries |
| C++20 compatibility example | Behavior/ABI checks passed; sampled runtime +9.74%, module code ratio 1.000 |
| C++17 compatibility example | Behavior/ABI checks passed; sampled runtime +13.25%, module code ratio 1.000 |
| Balanced fixture groups | 12 / 18 met the fixed +20% runtime / 2× module code caps |
| Formal task export | Rejected because some groups failed caps |
| One blind baseline/protected pilot pair | Both recovered candidates passed 124 / 124 hidden cases |
| Formal isolated paired matrix | Incomplete |
| Established anti-REA effectiveness | None |

## Balanced fixture samples

Times are one local matched sampling run, not guarantees for other machines. Measurements use warmup and 31 alternating samples. Short functions and borderline ratios are particularly sensitive to timing variation. Failed cases are not removed from acceptance.

| Category | Seed | Runtime increase | Module code ratio | Caps |
|---|---:|---:|---:|---|
| branch | 11 | 80.20% | 1.939 | fail |
| branch | 23 | 79.91% | 1.837 | fail |
| branch | 47 | 69.23% | 2.122 | fail |
| state | 11 | 8.81% | 1.538 | pass |
| state | 23 | 64.15% | 1.615 | fail |
| state | 47 | 31.73% | 1.538 | fail |
| parser | 11 | 1.46% | 1.379 | pass |
| parser | 23 | -1.93% | 1.379 | pass |
| parser | 47 | 1.79% | 1.379 | pass |
| table | 11 | 16.28% | 1.397 | pass |
| table | 23 | -2.65% | 1.298 | pass |
| table | 47 | -2.10% | 1.298 | pass |
| buffer | 11 | 30.10% | 1.238 | fail |
| buffer | 23 | 16.09% | 1.254 | pass |
| buffer | 47 | 7.56% | 1.264 | pass |
| callgraph | 11 | -1.82% | 1.353 | pass |
| callgraph | 23 | 4.72% | 1.353 | pass |
| callgraph | 47 | 0.52% | 1.353 | pass |

Run the current builder/verification commands to obtain fresh local reports; do not substitute this table for measurements on your build. Native CI checks behavior and transformations, not stable-machine performance acceptance.

## Pilot interpretation

Two fresh-context tool agents analyzed one anonymous task each with REA CLI/Ghidra and local execution, then supplied their own C++ candidates. Both baseline and protected candidates passed independent scorer tests over 124 cases. The protected branch was recovered successfully: local routing could be ignored and integer identities simplified.

The sessions used instruction-based access boundaries on a shared filesystem, not OS isolation. Only one category/seed was tested, model identity was not independently attested, no debugger tracing was evaluated, and compiler provisioning delays prevent a meaningful recovery-time ratio. The pilot is not three independent pairs or a complete blind/adaptive matrix. Its artifact hashes belonged to the original retained pilot packs, not later rebuilt targets.

Once the synthetic algorithms are published, searching this repository makes them available to an opponent. Future effectiveness experiments must use fresh unpublished tasks with independent isolation and auditable session records. Changed bytes, longer decompiler output or missing original source spelling are not substitutes for measured semantic recovery cost.
