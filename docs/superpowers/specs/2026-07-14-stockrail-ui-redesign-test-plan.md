# StockRail UI Redesign Test Plan

Date: 2026-07-14

## Test Strategy

This redesign changes user-facing layout, form behavior, and admin interactions without changing backend APIs. Verification must cover both automated behavior checks and rendered UI checks.

## Automated Checks

Run the full existing suite:

```bash
npm test
```

This covers:

- JavaScript unit tests.
- Python server tests.
- Storage and validation behavior.

## Targeted E2E Checks

Use the existing Playwright setup where practical:

```bash
npx playwright test
```

Required browser scenarios:

- Login redirects users by role.
- Member can open `/`, fill a valid order, add at least one inventory item, submit, and see success feedback.
- Member validation shows a field-level error for a missing required field and focuses the first invalid field.
- Invite copy button keeps a working success or fallback state.
- Avatar replacement still calls the existing profile update flow when a valid image is selected.
- Admin can open `/admin`, filter by keyword/status/delivery/date, select an order, and see detail.
- Admin can update status to `待处理`, `核对中`, and `已入库`.
- Superadmin can see user management and audit log sections.
- Superadmin can create a user and change a role if the existing seeded test flow supports it.

## Visual QA

Verify screenshots at these viewports:

- Mobile report page: 375 x 812.
- Mobile admin page: 390 x 844.
- Desktop admin page: 1440 x 900.
- Desktop login page: 1280 x 800.

Visual checks:

- No overlapping text or controls.
- No clipped buttons, badges, or table content that prevents use.
- Focus and invalid states are visible.
- Status badges use warning/info/success/neutral styling consistently.
- Empty states are bordered, concise, and visually aligned.
- Layout uses restrained operational styling, not a marketing hero or decorative card layout.
- Color usage is not dominated by one hue family.

## Manual Smoke Checks

Run the app:

```bash
npm start
```

Smoke paths:

1. Open `/login`.
2. Log in as a member.
3. Submit a valid report.
4. Continue to a new report.
5. Log in as admin or superadmin.
6. Open `/admin`.
7. Filter orders and clear filters.
8. Select an order and update its status.
9. Confirm user and audit sections for superadmin.

## Regression Risks

- Field-level error rendering may fail to clear stale messages.
- Dynamic item cards may lose add/delete/collapse behavior.
- Admin re-rendering may drop click handlers after status updates.
- Status badges may display escaped status text incorrectly if helper functions are not used consistently.
- Mobile admin tables may overflow if table wrappers are not constrained.

## Completion Evidence

The implementation is complete only when:

- The design spec remains consistent with the implemented scope.
- `npm test` passes.
- Targeted E2E checks pass or any skipped checks are explicitly justified.
- Screenshots or browser inspection confirm the required mobile and desktop layouts.
- `git diff` shows no unrelated backend, deployment, or generated-file churn.
