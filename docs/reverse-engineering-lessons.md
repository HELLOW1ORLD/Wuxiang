# Reverse-engineering lessons behind Wuxiang

These lessons come from an internal shipped-artifact recovery exercise. Original binaries, encryption material, private formats, recovery source and evidence archives are not distributed. This public note describes the methodology; readers cannot independently re-audit the private case from this repository.

| Observed obstacle | What changed the outcome | Consequence for evaluation |
|---|---|---|
| Large native binary exceeded full-analysis budgets | Focused entry points and persistent decompiler databases still recovered implementations | Include targeted attacks; a full-analysis timeout is not a protection result |
| Private format/version/type mappings were initially missing | Matching serialization layouts and runtime descriptors enabled useful recovery | Unknown formats add setup cost; adaptive agents can write parsers |
| Encrypted resources were inaccessible at first | Client registration code exposed usable key material, confirmed by container integrity checks | Evaluate key availability rather than treating encryption alone as permanent protection |
| Function meanings were unclear | Protocol schemas, RTTI, bindings, constants and call relationships provided semantic indexes | Leakage exists outside machine instructions and must remain in the attack model |
| Original source/editor data was absent | Extracted bytes and derived pseudocode did not yield the author's original project | Distinguish byte extraction, source spelling, behavior equivalence and editable-engine recovery |
| Some behavior depended on remote services | Client interfaces were found; absent remote implementations remained unavailable | Missing inputs cannot count as binary-protection effectiveness |

Keep observations, inference and untested scope distinct. Format parsing is not automatically a working plugin; pseudocode is not an equivalent compiled candidate; recovered resources are not a restored playable game. Successful output from one provider wrapper may still contain an inner timeout or backend failure.

Wuxiang therefore uses executable behavior tests, paired build conditions, per-function coverage and capped runtime/code-size measurements. It records capabilities and failures, allows public research/custom scripts, and includes known-design adaptive attacks. No conclusion should depend on an opponent never learning the transformation design.

The initial Wuxiang pilot also shows the limitation of simple obfuscation: volatile routing without business-visible effects can be ignored, and integer identities can be simplified. Increasing decompiler output length does not automatically increase semantic recovery cost. Future designs must earn a cost claim through fresh private tasks and independent paired sessions.
