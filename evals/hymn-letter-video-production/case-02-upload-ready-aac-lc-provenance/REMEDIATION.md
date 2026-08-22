# Eval remediation — revision 7 (2026-08-22)

Blind review rejected revision 6 on four remaining coverage gaps. Revision 7 changes the eval only:

1. Documentation grading now uses the exact frozen incident contract plus an explicit adversarial overclaim corpus independent of word order. The candidate mutation appends the reviewer-provided reordered direct-causality sentence and must fail.
2. Approval attacks independently replace decision, reviewer, and reviewed_at with nonempty valid-looking but unauthorized values, retain invalid-calendar-date coverage, and fully rebind all three fields in authority and receipt with `REJECTED`.
3. Sequence 02 now compares the exact authority track vector and fixed domain-separated composite. Each of the 12 tracks has its own full-rebinding attack that changes actual PCM/source hash and re-echoes authority, derivation, QC, and a recomputed composite.
4. Sequence 02/04/06 normalized encoder argv is an exact policy contract. Attacks cover input order, map order/value, output, duplicate required flags, arbitrary extra tokens, filter graphs, and every required flag value for every transcode profile.

Revision history:

- revision 5 frozen file: `111c034511be13f66ae0ce5d01db9990fa8f398e871a78f0e0ae33fd3734e4a3`
- revision 5 runner: `8925543cdb4b1690ee361bcf091ed7489e0d9a5c267a9d6f53a83c5f45cc8386`
- revision 6 runner: `4d45d54a206bc002e2a723c7811b5a4f758e04174e2622ef38dbb9cd0ebd148c`
- revision 6 self-test: `9/9`, 303/303 mutations rejected, exit 0
- revision 7 runner: `2692e1183ce3a149a4734d7f8fd4da3d34eae64787ab2f8eae4c92cc86ca1af5`
- revision 7 self-test: `9/9`, 355/355 mutations rejected, exit 0
- unmodified production snapshot: candidate exit 1 (pre-fix red)

No production asset or confirmed-case registry was changed.
