# Functional Spec

## Story

将 RukuFlow 入库报单系统商用化：增加 member/admin/superadmin 权限管理，admin 可查看报单表格，部署到 139 服务器 test.nexushome.top 并端到端验证，暂不使用容器

## Acceptance Criteria

1. The requested behavior is available in `order-report-system`.
2. The user-facing happy path is covered by tests or documented manual verification.
3. Invalid, empty, or unauthorized inputs are handled safely where applicable.
4. Existing behavior outside this story is preserved.

## Out of Scope

- Production release automation
- Silent changes to unrelated repositories
- Bypassing CI, review, or branch protection
