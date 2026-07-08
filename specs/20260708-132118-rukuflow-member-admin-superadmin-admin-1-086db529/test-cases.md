# Test Cases

## From Test Plan

# Test Plan

## Required Checks

1. Add or update unit tests for the changed behavior.
2. Run the repository's normal build or typecheck command.
3. Run integration tests if the story changes API, storage, auth, payment, quota, or external service behavior.
4. Record manual verification steps when automation is not yet available.

## Edge Cases

- Empty or malformed input
- Unauthorized or unsupported user state
- Existing behavior outside the story
- Retry or duplicate action where applicable

## From E2E Plan

```yaml
e2e_cases:
  - id: E2E-001
    title: Verify the requested story through the primary user flow
    repo: order-report-system
    steps:
      - open the affected user flow
      - perform the action described by the story
      - assert the expected visible outcome
      - assert unrelated critical flows still load

```
