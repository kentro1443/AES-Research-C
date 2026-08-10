# Draft errata — issues to fix in `draft1.pdf` before the next revision

These are inconsistencies between the current draft (Introduction + Methodology)
and the experiments actually run. Ordered by importance.

1. **Retained-run identity (Table 1).** The draft fixes the retained threshold
   run as seed **10053** (Table 1). The paper now anchors C on seed **4175**
   (the cleanest run, N50 ≈ 51k), with seed 10053 kept only as a variability
   replicate and the earliest run (seed 23394) excluded as contaminated. Update
   Table 1's seed and add a one-line provenance/collector-identity note. All runs
   share commit `405b3de` (working tree dirty — state this).

2. **"Only one validated threshold run" (Sec 2.1, 2.14).** No longer true. The
   paper now reports a canonical C threshold **plus** a cross-language recovery
   comparison, a garbage-collector ablation, a dial sweep, and a C replicate.
   Revise these passages and the RQ/hypothesis scoping accordingly.

3. **RQ2 / RQ3 mismatch.** The draft frames the cross-language study as
   shared-dataset *consistency* (RQ2) and stage-level *processing time* (RQ3).
   Neither was run. What was run is **native per-language collection + recovery
   reliability** — a different experiment the draft itself flags as "a separate
   runtime-dependent experiment" (Sec 1.2.5, 2.11). Add a new RQ for it (and its
   hypothesis: managed-runtime collection raises the trace threshold), and keep
   RQ2/RQ3 explicitly as future work.

4. **Confound disclosure.** State plainly that the cross-language comparison uses
   each language's own traces (different seeds), so it isolates
   runtime-in-collection, *not* algorithmic consistency. Without this the reader
   may conflate it with the Sec 2.11 shared-dataset plan.

5. **Broken cross-reference.** p.4: H1 is "evaluated by the retained threshold run
   described in Section **??**." Fix the reference.

6. **Reference error (`ref.md` / bibliography).** Reference [4] (Bonneau–Mironov,
   CHES 2006) is cited with an ACM DOI (`10.1145/1128817.1128887`) that actually
   resolves to a *different* paper — Neve, Seifert & Wang, "A Refined Look at
   Bernstein's AES Side-Channel Analysis" (ASIACCS 2006). Fix the [4] citation to
   the Springer CHES 2006 entry. Since Neve–Seifert–Wang is now used for context,
   add it as its own reference.

## Smaller notes / suggestions

- The draft's stated prior-work band "2^15–2^16" for the attack is looser than
  Bonneau–Mironov's actual Table 3 figures (median 2^13–2^14.3 with L2 eviction
  for the expanded final-round attack). Use the specific numbers.
- Methodology should add the dial-sweep design (and the rationale for the fixed
  100k count), the GC ablation, and the dataset-governance rules — see
  `methodology_additions.tex`.
