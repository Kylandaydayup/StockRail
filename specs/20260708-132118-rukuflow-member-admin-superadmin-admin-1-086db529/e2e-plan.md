e2e_cases:
  - id: E2E-001
    title: Verify the requested story through the primary user flow
    repo: order-report-system
    steps:
      - open the affected user flow
      - perform the action described by the story
      - assert the expected visible outcome
      - assert unrelated critical flows still load
