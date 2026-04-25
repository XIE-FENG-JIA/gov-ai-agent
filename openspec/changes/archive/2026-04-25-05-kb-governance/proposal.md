## Problem

Epic 5 already proved the end-to-end rewrite flow can generate five traced DOCX
outputs, and the repo now keeps nine real corpus files plus guards that reject
fixture-backed evidence in rewrite and verify paths. But the knowledge-base
governance boundary is still implicit across scattered code paths instead of one
approved change package:

- `src/sources/ingest.py` decides when fixture fallback is allowed and when
  `require_live` MUST fail loudly
- `src/cli/kb/rebuild.py` now supports `--only-real`, but there is no approved
  contract for when rebuilds MUST exclude `synthetic` or `fixture_fallback`
  records
- `src/e2e_rewrite.py` and `src/cli/verify_cmd.py` already skip synthetic or
  fixture-backed corpus entries, but that rule is not written as a stable
  knowledge-base requirement
- `tests/test_corpus_provenance_guard.py` enforces the current corpus state, but
  the repo still lacks one governance proposal that defines provenance,
  rebuild, and retirement expectations together

Without a formal Epic 5 proposal, future cleanup work risks drifting between
CLI flags, ingest behavior, Chroma rebuild habits, and ad hoc corpus hygiene.
That would reopen the same failure mode Epic 1 just closed: fake-green corpus
state where fallback data silently mixes into production rewrite and verify
flows.

## Solution

Create change `05-kb-governance` as the repo-owned contract for knowledge-base
governance in Gov AI Agent. The first slice stays narrow and operational:

- define provenance governance for `kb_data/corpus/`, including the rule that
  production rewrite, verify, and rebuild paths treat `synthetic` and
  `fixture_fallback` as exclusion signals unless a task explicitly opts in
- define the approved rebuild boundary around `gov-ai kb rebuild --only-real`
  so real-source indexing can be refreshed without reintroducing fixture-backed
  documents into the active retrieval set
- define corpus hygiene and retirement expectations for fixture-backed or stale
  artifacts, including loud failure when a supposedly live flow falls back to
  fixtures
- define the first governance checkpoints that future Epic 5 tasks must cover:
  provenance guard, only-real rebuild, corpus retirement/archive policy, and
  post-rebuild verification against repo evidence

This proposal does not lock the final storage backend today. ChromaDB can
remain the active index while SurrealDB migration stays frozen. The proposal
fixes the behavior boundary instead: the repo must have one explicit rule for
which corpus entries are eligible for active retrieval and how operators verify
that eligibility after ingest or rebuild.

## Non-Goals

- No storage migration or SurrealDB rollout in this change
- No new ingestion source onboarding by itself
- No benchmark or blind-eval work
- No redesign of the five-agent review stack or export metadata contract

## Acceptance Criteria

1. `openspec/changes/05-kb-governance/proposal.md` exists and defines Epic 5 as
   a knowledge-base governance boundary, not just a one-off cleanup task.
2. The proposal names provenance exclusion rules for `synthetic` and
   `fixture_fallback` corpus entries across ingest, rebuild, rewrite, and
   verify flows.
3. The proposal defines `gov-ai kb rebuild --only-real` and corpus-retirement
   policy as the first required Epic 5 implementation slices.
4. Follow-up Epic 5 tasks can map directly to governance work without reopening
   what counts as active, trusted repo evidence.
