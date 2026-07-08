# StockRail 库存轨道

StockRail 是一个轻量的入库报单系统。用户在手机页面提交报单，管理员在后台查看订单详情。

## 页面

- `index.html`：用户报单登记页
- `admin.html`：管理员订单列表和详情页

## 本地运行

```bash
npm install
npm start
```

打开：

```text
http://localhost:4173/
http://localhost:4173/admin.html
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

## 注册与微信登录

- 普通注册会创建 `member` 用户。
- 微信资料登录会创建或复用 `member` 用户，并把页面展示名设置为微信昵称、头像设置为微信头像。
- 当前仓库内置的是可部署验证的微信资料登录入口；真实微信 OAuth 需要配置微信开放平台或公众号的 AppID、AppSecret、授权回调域名。

真实微信 OAuth 的服务端配置建议预留为：

```bash
export WECHAT_APP_ID='your-app-id'
export WECHAT_APP_SECRET='your-app-secret'
export WECHAT_REDIRECT_URI='http://test.nexushome.top/api/wechat/callback'
```

没有这些凭证时，系统不会伪造已接入微信官方 OAuth，只提供受控的资料登录流程用于业务闭环验证。

首次启动时会根据环境变量创建超级管理员：

```bash
export STOCKRAIL_SUPERADMIN_USER=superadmin
export STOCKRAIL_SUPERADMIN_PASSWORD='change-this-password'
export STOCKRAIL_SESSION_SECRET='change-this-secret'
python3 server.py
```

## 生产部署（非容器）

推荐用 systemd 托管 Python 进程，Nginx 反代到本机端口。

```text
Browser -> Nginx :80 test.nexushome.top -> 127.0.0.1:4173 -> StockRail Python server -> SQLite
```

服务默认监听 `127.0.0.1:4173`，数据默认写入 `data/stockrail.db`。生产环境建议通过 `STOCKRAIL_DB` 指向稳定路径。
