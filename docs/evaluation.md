# Evaluation protocol and public-source boundary

The goal is to increase the cost of recovering selected behavior, not to preserve source spelling. Missing comments, a failed tool, an analysis timeout, or missing server-side inputs are not evidence of effective protection.

## Public fixtures versus fresh evaluation targets

`bench/tasks.cpp` and `python/wuxiang/bench.py` publish the bundled algorithms and test generators. Their native differential tests measure engineering correctness. Once this repository is public, an agent allowed public research can retrieve these algorithms; the six fixtures cannot establish anti-recovery effectiveness.

Formal evaluation needs independently designed, unpublished tasks and tests. Do not publish their source, seed-to-artifact mapping, hidden cases or completed candidates during the evaluation. Add the fresh tasks to a private evaluation copy of the benchmark builder/reference generator with matching public interfaces. The v0.1 scorer is specialized to six fixture categories; supporting arbitrary private tasks requires a private adapter and separate validation, not merely passing a different EXE path.

## Matched builds and budgets

Use the same optimized LLVM pipeline for baseline/protected targets, with the same interface, symbol conditions, CRT and optimization flags. MSVC originals are separate compiler controls. Every selected function must pass behavior/ABI checks and the fixed runtime ≤1.20× and COFF module `.text` ≤2× limits before claiming balanced acceptance.

Use the same model/version, REA/backend versions, tools and capabilities. Allow focused decompilation, public research, custom scripts and, when available, execution/debugging/tracing. Default session budget: 1,800 seconds and 100 tool calls. Begin timing when the target and tools are ready; distinguish compiler provisioning from recovery work.

Run blind and adaptive sessions with fresh contexts and randomized order. Adaptive sessions receive the public protection design. For six categories × three seeds × two modes, three independent pairs per group require 108 pairs / 216 baseline/protected sessions. Do not reuse a candidate or transcript between sessions. Record actual unique session IDs, pair IDs, tool events and capability gaps; the time limit is not a fabricated recovery time.

## Environment separation and scoring

Attack environments receive only one target, its API and permitted public information. They must not mount source, scorer files, hidden tests, mappings or other session results. Use separate clean VM snapshots or equivalent OS access boundaries for attacks and native candidate compilation/execution. There is no such sandbox built into the v0.1 scorer.

Candidate code is actually compiled with the trusted harness and checked against return values and the entire output buffer, including unwritten canary bytes. Compilation errors, execution errors, budget violations, tool errors, timeouts and semantic failures are distinct outcomes. Successful hidden tests demonstrate agreement over the tested domain, not a proof for every input.

Local scores are marked `score_integrity: not_attested` and `hidden_tests_access_protected: false`; independent isolation and environment audits are required for formal interpretation. Session data is imported, not independently verified. Tool version/configuration discovery alone does not prove a backend works or that an AI attack ran. Missing dynamic analysis is `unevaluated`.

## Interpretation

Matched successful reconstructions yield time/tool-call comparisons; unsuccessful recovery remains a censored result. Report all attempts and variation, not just one difficult target. Public design knowledge, surrounding code and interfaces may let agents simplify the protection. Changed machine instructions are an engineering check, not proof of increased recovery cost.

The initial pilot restored the protected branch. See [observations](results.md); no formal anti-REA claim is made.
