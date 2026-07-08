---
name: storyrail-ship
description: Trigger StoryRail from a short product story and report milestone progress only.
---

# StoryRail Ship

1. Run `storyrail workspace detect --json`.
2. Run `storyrail ship "<story>" --repo <repo> --until tasks --agent codex`.
3. Run `storyrail status --run <run-id> --agent-summary`.
4. Do not implement outside `specs/<run-id>/tasks.yaml`.
5. Use `storyrail deliver --run <run-id>` for local checks, preview, E2E, and acceptance.
6. Use `storyrail publish --run <run-id> --push --pr --watch-ci` only after local acceptance passes.
