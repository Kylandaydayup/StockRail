# StockRail UI Redesign Design

Date: 2026-07-14

## Objective

Refactor the StockRail order report experience and improve the interface by using `/Users/bytedance/dev/drama/ui-design-kit` as the design reference.

The current project is a no-build native HTML/CSS/JavaScript app. This redesign will not introduce React, Tailwind, or a bundler in this phase. Instead, it will migrate the design kit's token, form, feedback, and status-display patterns into the existing app.

## Scope

In scope:

- User order report page at `/`.
- Admin order workspace at `/admin`.
- Shared visual system in `src/styles.css`.
- Small JavaScript changes needed to support field-level errors, status badge variants, loading, empty, and feedback states.
- Minimal login/register visual alignment where global styles affect the page.

Out of scope:

- Replacing the app with React.
- Changing backend APIs or the SQLite storage schema.
- Changing authentication, registration, invite, role, or audit-log rules.
- Adding new business statuses beyond the existing `待处理`, `核对中`, and `已入库`.
- Building reusable package exports from this repository.

## Design Source

Reference files:

- `/Users/bytedance/dev/drama/ui-design-kit/src/styles/tokens.css`
- `/Users/bytedance/dev/drama/ui-design-kit/docs/design-principles.md`
- `/Users/bytedance/dev/drama/ui-design-kit/docs/form-guidelines.md`
- `/Users/bytedance/dev/drama/ui-design-kit/docs/feedback-guidelines.md`
- `/Users/bytedance/dev/drama/ui-design-kit/docs/component-inventory.md`

Applied principles:

- Use semantic tokens instead of ad hoc colors.
- Keep operational screens quiet, dense, and scannable.
- Prefer 1px borders over decorative shadows.
- Use moderate radii derived from a single radius token.
- Place field errors under their related fields.
- Use banners only for page-level messages.
- Use status badges only for real status, not arbitrary categorization.
- Use consistent empty, error, and loading states in lists and panels.

## Visual System

`src/styles.css` will be reorganized around design-kit-like CSS custom properties:

- Surface tokens: `--background`, `--foreground`, `--card`, `--muted`, `--muted-foreground`.
- Border and focus tokens: `--border`, `--input`, `--ring`.
- Action tokens: `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`.
- Feedback tokens: `--destructive`, `--success`, `--warning`, `--info`, and foreground variants.
- Radius tokens derived from `--radius`.

The palette should remain neutral and utility-focused. Avoid a one-note blue, purple, beige, or decorative gradient theme. Primary color can be dark neutral with blue reserved for information and focus affordances.

Controls should share a common base:

- Inputs, textareas, and selects use visible borders, stable height, focus ring, and invalid state.
- Buttons use variants equivalent to default, secondary, outline, ghost, and destructive.
- Compact icon-sized buttons have stable square dimensions.
- Panels and cards use borders with minimal or no shadow.

## User Report Page

The report page remains mobile-first and must still work well at desktop widths.

Information architecture:

1. Header
   - StockRail identity.
   - Current user badge with avatar when available.
   - Admin link when present in the existing markup.
   - Close action keeps current toast behavior.

2. Account and invite area
   - Current profile and avatar replacement stay available.
   - Invite summary becomes a compact bordered panel.
   - Copy invite action keeps existing clipboard fallback behavior.

3. Basic order information
   - WeChat name.
   - Delivery method.
   - Tracking numbers.
   - Total boxes.

4. Inventory items
   - Each item remains an editable card.
   - Existing actions remain: add, delete, collapse, expand, and show helper text.
   - Item cards become denser and use consistent field layout.
   - At least one item remains required.

5. Contact and notes
   - Total cans.
   - Phone.
   - Remark.

6. Submission feedback
   - Field-level errors appear below the relevant fields.
   - A page-level error summary may remain for the first error.
   - Successful submission uses a clear success panel/sheet and keeps the "continue report" action.

Behavioral requirements:

- Existing validation behavior from `validateOrder` remains authoritative.
- JavaScript maps validation keys to field error nodes.
- First invalid field receives focus.
- Submit button disabled/loading behavior remains.
- Toast remains for short confirmations.

## Admin Workspace

The admin page becomes a SaaS-style workspace optimized for repeated scanning and status updates.

Layout:

- Top header with product name, page title, current user, return link, and logout.
- Main workspace with a filter/list region and a detail region.
- Desktop uses a two-column master-detail layout.
- Mobile stacks filters, list, and detail without horizontal overflow.

Order filters:

- Keyword, status, delivery method, start date, and end date stay functionally identical.
- Filter controls become a compact toolbar/grid.
- Reset and submit actions use consistent button variants.

Order list:

- Empty state uses a bordered panel with title and short description.
- Rows remain clickable and preserve selected order behavior.
- Active row uses a semantic selected state rather than heavy decoration.
- Status column renders a badge:
  - `待处理`: warning
  - `核对中`: info
  - `已入库`: success
  - unknown: neutral

Order detail:

- Detail header shows customer name, status badge, and created time.
- Order fields use a definition-grid layout for quick scanning.
- Item table remains available.
- Status actions are grouped and keep the existing PATCH API behavior.

Superadmin sections:

- User and permission management stays visible only for `superadmin`.
- Audit log stays visible only for `superadmin`.
- Tables and empty states use the same admin visual language.
- Role select behavior remains unchanged.

## Error, Empty, and Loading States

The implementation will add CSS and markup patterns equivalent to:

- `AlertBanner` for page-level success, warning, info, and destructive messages.
- `EmptyState` for empty order list, empty detail, empty users, and empty audit logs.
- `LoadingState` for pending render operations where feasible without large architectural changes.
- `StatusBadge` for order status.

Errors from API calls should remain user-visible. The current API helper behavior is not changed.

## Accessibility

- Inputs with validation errors use `aria-invalid="true"`.
- Error text uses stable elements and can be referenced with `aria-describedby` where practical.
- Buttons keep `type="button"` unless they submit a form.
- Icon-like controls keep accessible labels.
- Focus states are visible.
- Touch targets remain usable on mobile.

## Implementation Boundaries

Expected changed files during implementation:

- `index.html`
- `admin.html`
- `login.html` only if shared style changes require small class alignment.
- `src/styles.css`
- `src/app.js`
- `src/admin.js`
- Tests under `tests/` or `e2e/` as needed.

Backend files should not change unless a test reveals an existing incompatibility with the UI contract.

## Acceptance Criteria

- The app keeps the current no-build startup flow: `npm start`.
- `npm test` passes.
- Member users can submit an order from `/`.
- Admin and superadmin users can view, filter, select, and update orders from `/admin`.
- Superadmin users can still create users, change roles, and view audit logs.
- Visual styling clearly reflects the design kit's token, form, feedback, and status patterns.
- Mobile report page has no obvious overlap, clipped controls, or unreadable text at 375px width.
- Desktop admin page has no horizontal overflow in the main workspace at common laptop widths.
- Existing invite copy fallback, avatar replacement, and continue-report flow still work.
