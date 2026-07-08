# StockRail

StockRail 是一个轻量的入库报单系统。用户在手机页面提交报单，管理员在后台查看订单详情。

## 页面

- `/`：用户报单登记页
- `/admin`：管理员订单列表和详情页

## 本地运行

```bash
npm install
npm start
```

打开：

```text
http://localhost:4173/
http://localhost:4173/admin
```

## 测试

```bash
npm test
```

## 数据

当前版本使用服务端 SQLite 保存订单，支持 `member`、`admin`、`superadmin` 三种角色。

## 权限

- `member`：提交报单，查看自己的数据。
- `admin`：查看报单表格、订单详情、修改订单状态。
- `superadmin`：拥有 admin 能力，并可以创建 `member`、`admin`、`superadmin` 用户。

## 注册

- 普通注册使用邮箱 + 6 位验证码，会创建 `member` 用户。
- 注册时可填写昵称，并直接上传头像图片用于页面展示；登录后也可以替换头像。
- 登录支持邮箱或用户名。
- 忘记密码使用同一邮箱验证码体系重置密码。
- 系统不包含微信登录入口。

邮箱验证码使用与 Blue-Console 一致的 SMTP 环境变量：

```bash
export SMTP_HOST=smtp.qq.com
export SMTP_PORT=587
export SMTP_USERNAME='your-mail@qq.com'
export SMTP_PASSWORD='your-smtp-auth-code'
export SMTP_FROM='your-mail@qq.com'
export REGISTER_CODE_TTL=10m
export REGISTER_CODE_COOLDOWN=60s
export ALLOW_INSECURE_MAIL_LOG=false
```

验证码邮件使用 StockRail 品牌模板，包含品牌名、验证码、有效期和安全提醒。

## 邀请码

每个用户都有自己的邀请链接。别人通过该链接注册后：

- 新用户仍然是 `member`，不会自动获得 admin 权限。
- 系统会记录邀请关系。
- 邀请人可以在报单页看到“已邀请 N 人”。
- 后续可在此基础上扩展返佣、额度、团队、代理层级等商业规则。

## 管理员筛选

管理员订单表支持按微信名字、快递单号、手机号、用户名关键词筛选，也支持按状态、交货方式和日期范围过滤。

首次启动时会根据环境变量创建超级管理员：

```bash
export STOCKRAIL_SUPERADMIN_USER=superadmin
export STOCKRAIL_SUPERADMIN_EMAIL=superadmin@example.com
export STOCKRAIL_SUPERADMIN_PASSWORD='change-this-password'
export STOCKRAIL_SESSION_SECRET='change-this-secret'
python3 server.py
```

`superadmin` 可以在后台用户与权限区域把已有用户设置为 `admin`、`member` 或 `superadmin`。

## 审计日志

系统会记录重要操作审计日志，包括用户注册、忘记密码重置、资料修改、创建用户、修改角色、提交报单、修改订单状态。

- 只有 `superadmin` 可以查看审计日志。
- 系统不提供审计日志删除接口。
- 审计日志用于追踪关键操作，不应作为普通业务数据清理。

## 生产部署（非容器）

推荐用 systemd 托管 Python 进程，Nginx 反代到本机端口。

```text
Browser -> Nginx :80 test.nexushome.top -> 127.0.0.1:4173 -> StockRail Python server -> SQLite
```

服务默认监听 `127.0.0.1:4173`，数据默认写入 `data/stockrail.db`。生产环境建议通过 `STOCKRAIL_DB` 指向稳定路径。
