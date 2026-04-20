# Tasks: 02-open-notebook-fork

- [ ] **T2.0** Vendor or clone `lfnovo/open-notebook` into `vendor/open-notebook` and confirm the repo can import it.  
  Validation: `python -c "import sys; sys.path.insert(0, 'vendor/open-notebook'); print('ok')"`  
  Commit: `chore(vendor): add open-notebook fork target`

- [ ] **T2.1** Study the vendored runtime and write `docs/open-notebook-study.md` covering entrypoints, ask-service flow, and extension seams.  
  Validation: `rg -n "ask_service|router|retriev|notebook" docs/open-notebook-study.md`  
  Commit: `docs(integration): study open-notebook runtime seams`

- [ ] **T2.2** Write `docs/integration-plan.md` choosing the repo-owned integration seam between `src/` and `vendor/open-notebook`.  
  Validation: `rg -n "integration seam|fallback|review agents|vendor/open-notebook" docs/integration-plan.md`  
  Commit: `docs(integration): define gov-ai and open-notebook boundary`

- [ ] **T2.3** Add a repo-owned service adapter for ask-style calls that wraps vendored runtime imports behind one module.  
  Validation: `pytest tests/test_open_notebook_service.py -q`  
  Commit: `feat(integration): add open-notebook service adapter`

- [ ] **T2.4** Add a smoke CLI or script path that exercises one minimal ask-style request without replacing production writer flow.  
  Validation: `pytest tests/test_open_notebook_smoke.py -q`  
  Commit: `feat(cli): add open-notebook smoke path`

- [ ] **T2.5** Wire `src/agents/writer.py` to call the new service adapter behind a feature flag or explicit runtime toggle.  
  Validation: `pytest tests/test_writer_agent.py -q`  
  Commit: `feat(writer): add optional open-notebook ask-service path`

- [ ] **T2.6** Expose retrieved evidence from the service adapter so fact checker and citation checker can inspect the same payload.  
  Validation: `pytest tests/test_open_notebook_service.py tests/test_agents.py -q`  
  Commit: `feat(integration): preserve ask-service evidence for review agents`

- [ ] **T2.7** Define and implement fallback behavior when the vendor path is missing or ask-service initialization fails.  
  Validation: `pytest tests/test_open_notebook_service.py -q -k fallback`  
  Commit: `fix(integration): fail clearly and preserve legacy writer fallback`

- [ ] **T2.8** Add docs and operator notes for required env vars, local setup, and the current non-goals of the fork integration.  
  Validation: `rg -n "OPENROUTER_API_KEY|elephant-alpha|non-goals|legacy writer" docs/open-notebook-study.md docs/integration-plan.md`  
  Commit: `docs(integration): document setup and non-goals for fork adoption`

- [ ] **T2.9** Request human review before any SurrealDB migration or full writer cutover proceeds.  
  Validation: `rg -n "human review|required before SurrealDB|frozen" docs/integration-plan.md openspec/changes/02-open-notebook-fork/specs/fork/spec.md`  
  Commit: `docs(integration): freeze storage migration until review`
