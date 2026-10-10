# Contributing

Start with [usage](docs/usage.zh-CN.md) and [evaluation boundaries](docs/evaluation.md). The initial release targets Windows x64, MSVC and LLVM 20.1.8 only.

For a behavior-changing transform, add a regression demonstrating the bug or unsupported case, verify transformed IR, and compare native behavior including memory effects and exceptions. Use defined integer semantics. Record coverage limitations and machine-code survival; never silently report protection when no selected site was transformed.

Run:

```powershell
python tools/bootstrap_llvm.py
python wuxiang.py protect --config examples/compat.json
python -m unittest discover -s tests -v
python tools/audit_source.py
```

Do not submit toolchains, binaries, proprietary artifacts, keys, private scoring data or session evidence containing credentials. Performance claims need the fixed 20%/2× caps and raw matched measurements. Anti-recovery claims additionally need new unpublished tasks and audited independent attack sessions. Recovered public fixtures alone do not establish effectiveness.

Describe the concrete behavior change, tests run and limitations in pull requests. Report bypasses with toy inputs or minimal reproductions. Contributions are made under this repository's license. See [SECURITY](SECURITY.md) for private disclosure options.
