# Draft authorization and MySQL evidence remediation

User-approved scope: P1 authenticated buyer draft creation with transactional creator audit,
owner-only replay/submission; P2 current service evidence in MySQL tests; fresh page acceptance.

- [x] Add signed-token regressions for anonymous/wrong role, owner visibility, cross-buyer submission/replay, single creation audit and rollback; run to expose current failures.
- [x] In main.py enforce buyer auth, check existing order owner before replay, create audit in the draft transaction, check submission owner before state transitions. Preserve existing internal service contracts and evidence validation.
- [x] Update existing HTTP test helpers to log in. Prepare MySQL drafts using forecast/recommendation services and both latest-evidence markers in Mock Agent calls. Preserve concurrency, duplicate, stale-version, rollback and reconnect assertions.
- [x] Run focused tests, complete backend suite, opt-in MySQL suite with report, frontend build.
- [x] Restart local backend with changed code, use browser for two real draft/submit flows, approve one, restart with the other pending and reject after recovery. Save screenshots and database evidence.
- [x] Refresh acceptance report, API docs, project/roadmap and local handoff/task/memory/decisions; review diff and verification evidence.
