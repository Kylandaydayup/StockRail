#!/usr/bin/env python3
import base64
import binascii
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from email.utils import parseaddr
from urllib.parse import parse_qs, urlparse


APP_ROOT = Path(__file__).resolve().parent
ROLES = {"member", "admin", "superadmin"}


def create_app(config=None):
    config = config or {}
    db_path = config.get("db_path") or os.environ.get("STOCKRAIL_DB", str(APP_ROOT / "data" / "stockrail.db"))
    app = StockRailApp(
        db_path=db_path,
        upload_dir=config.get("upload_dir") or os.environ.get("STOCKRAIL_UPLOAD_DIR", str(APP_ROOT / "uploads")),
        session_secret=config.get("session_secret") or os.environ.get("STOCKRAIL_SESSION_SECRET", "dev-session-secret"),
        superadmin_username=config.get("superadmin_username") or os.environ.get("STOCKRAIL_SUPERADMIN_USER", "superadmin"),
        superadmin_email=config.get("superadmin_email") or os.environ.get("STOCKRAIL_SUPERADMIN_EMAIL", "superadmin@stockrail.local"),
        superadmin_password=config.get("superadmin_password") or os.environ.get("STOCKRAIL_SUPERADMIN_PASSWORD", "ChangeMe123!"),
        mailer=config.get("mailer") or SMTPMailer.from_env(),
        register_code_ttl=int(config.get("register_code_ttl_seconds") or os.environ.get("REGISTER_CODE_TTL_SECONDS") or duration_env("REGISTER_CODE_TTL", 600)),
        register_code_cooldown=int(config.get("register_code_cooldown_seconds") or os.environ.get("REGISTER_CODE_COOLDOWN_SECONDS") or duration_env("REGISTER_CODE_COOLDOWN", 60)),
    )
    app.init_db()
    return app


class StockRailApp:
    def __init__(
        self,
        db_path,
        upload_dir,
        session_secret,
        superadmin_username,
        superadmin_email,
        superadmin_password,
        mailer,
        register_code_ttl,
        register_code_cooldown,
    ):
        self.db_path = db_path
        self.upload_dir = Path(upload_dir)
        self.session_secret = session_secret.encode("utf-8")
        self.superadmin_username = superadmin_username
        self.superadmin_email = normalize_email(superadmin_email)
        self.superadmin_password = superadmin_password
        self.mailer = mailer
        self.register_code_ttl = register_code_ttl
        self.register_code_cooldown = register_code_cooldown

    def connect(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists users (
                  id integer primary key autoincrement,
                  username text not null unique,
                  email text not null default '',
                  password_hash text not null,
                  role text not null check(role in ('member','admin','superadmin')),
                  nickname text not null default '',
                  avatar_url text not null default '',
                  invite_code text not null default '',
                  invited_by integer,
                  created_at text not null
                );
                create table if not exists sessions (
                  token_hash text primary key,
                  user_id integer not null,
                  expires_at integer not null,
                  created_at text not null,
                  foreign key(user_id) references users(id)
                );
                create table if not exists orders (
                  id text primary key,
                  user_id integer not null,
                  status text not null,
                  wechat_name text not null,
                  delivery_method text not null,
                  tracking_numbers text not null,
                  total_boxes integer not null,
                  total_cans integer not null default 0,
                  phone text not null,
                  remark text not null default '',
                  created_at text not null,
                  foreign key(user_id) references users(id)
                );
                create table if not exists order_items (
                  id integer primary key autoincrement,
                  order_id text not null,
                  brand text not null,
                  product text not null,
                  quantity integer not null,
                  foreign key(order_id) references orders(id) on delete cascade
                );
                create table if not exists verification_codes (
                  purpose text not null,
                  email text not null,
                  code_hash text not null,
                  expires_at integer not null,
                  cooldown_until integer not null,
                  created_at text not null,
                  primary key(purpose, email)
                );
                create table if not exists audit_logs (
                  id integer primary key autoincrement,
                  actor_user_id integer,
                  actor_email text not null default '',
                  actor_role text not null default '',
                  action text not null,
                  target_type text not null default '',
                  target_id text not null default '',
                  details_json text not null default '{}',
                  created_at text not null
                );
                """
            )
            ensure_user_column(conn, "email", "text not null default ''")
            ensure_user_column(conn, "nickname", "text not null default ''")
            ensure_user_column(conn, "avatar_url", "text not null default ''")
            ensure_user_column(conn, "invite_code", "text not null default ''")
            ensure_user_column(conn, "invited_by", "integer")
            self.backfill_users(conn)
            conn.execute("create unique index if not exists idx_users_email on users(email)")
            conn.execute("create unique index if not exists idx_users_invite_code on users(invite_code)")
            user = conn.execute("select id from users where username = ?", (self.superadmin_username,)).fetchone()
            if user is None:
                conn.execute(
                    """
                    insert into users(username, email, password_hash, role, nickname, invite_code, created_at)
                    values(?,?,?,?,?,?,?)
                    """,
                    (
                        self.superadmin_username,
                        self.superadmin_email,
                        hash_password(self.superadmin_password),
                        "superadmin",
                        "超级管理员",
                        generate_invite_code(),
                        now_iso(),
                    ),
                )
            else:
                conn.execute(
                    "update users set email = coalesce(nullif(email, ''), ?), invite_code = coalesce(nullif(invite_code, ''), ?) where id = ?",
                    (self.superadmin_email, generate_invite_code(), user["id"]),
                )

    def backfill_users(self, conn):
        users = conn.execute("select id, username, email, invite_code from users").fetchall()
        for user in users:
            email = user["email"] or user["username"] if is_valid_email(user["username"]) else f"user-{user['id']}@stockrail.local"
            invite_code = user["invite_code"] or generate_invite_code()
            conn.execute("update users set email = ?, invite_code = ? where id = ?", (email, invite_code, user["id"]))

    def handle_test_request(self, method, path, headers=None, body=None):
        headers = headers or {}
        body_bytes = b""
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")
            headers = {**headers, "Content-Type": "application/json"}
        status, response_headers, raw_body = self.dispatch(method, path, headers, body_bytes)
        parsed = None
        if response_headers.get("Content-Type", "").startswith("application/json") and raw_body:
            parsed = json.loads(raw_body.decode("utf-8"))
        return {"status": status, "headers": response_headers, "body": raw_body, "json": parsed}

    def dispatch(self, method, raw_path, headers, body):
        parsed = urlparse(raw_path)
        path = parsed.path
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            if path.startswith("/api/"):
                return self.dispatch_api(method, path, query, headers, body)
            return self.serve_static(path)
        except HTTPError as exc:
            return json_response(exc.status, {"error": exc.message})
        except Exception as exc:
            return json_response(500, {"error": "internal server error", "detail": str(exc)})

    def dispatch_api(self, method, path, query, headers, body):
        if method == "POST" and path == "/api/login":
            return self.login(read_json(body))
        if method == "POST" and path == "/api/register/code":
            return self.send_verification_code("register", read_json(body))
        if method == "POST" and path == "/api/register":
            return self.register(read_json(body))
        if method == "POST" and path == "/api/password-reset/code":
            return self.send_verification_code("password-reset", read_json(body), require_existing=True)
        if method == "POST" and path == "/api/password-reset":
            return self.reset_password(read_json(body))
        if method == "POST" and path == "/api/logout":
            user = self.require_user(headers)
            self.logout(headers, user)
            return json_response(200, {"ok": True})
        if method == "GET" and path == "/api/me":
            user = self.require_user(headers)
            return json_response(200, {"user": public_user(user)})
        if method == "PATCH" and path == "/api/me/profile":
            user = self.require_user(headers)
            return json_response(200, {"user": self.update_profile(user, read_json(body))})
        if method == "GET" and path == "/api/invite":
            user = self.require_user(headers)
            return json_response(200, self.get_invite_info(user, headers))
        if method == "GET" and path == "/api/orders":
            user = self.require_user(headers)
            return json_response(200, {"orders": self.list_orders(user, query)})
        if method == "POST" and path == "/api/orders":
            user = self.require_user(headers)
            return json_response(201, {"order": self.create_order(user, read_json(body))})
        if method == "GET" and path.startswith("/api/orders/"):
            user = self.require_user(headers)
            return json_response(200, {"order": self.get_order(user, path.rsplit("/", 1)[-1])})
        if method == "PATCH" and path.startswith("/api/orders/") and path.endswith("/status"):
            user = self.require_role(headers, {"admin", "superadmin"})
            order_id = path.split("/")[-2]
            return json_response(200, {"order": self.update_order_status(user, order_id, read_json(body))})
        if method == "GET" and path == "/api/users":
            self.require_role(headers, {"superadmin"})
            return json_response(200, {"users": self.list_users()})
        if method == "POST" and path == "/api/users":
            actor = self.require_role(headers, {"superadmin"})
            return json_response(201, {"user": self.create_user(actor, read_json(body))})
        if method == "PATCH" and path.startswith("/api/users/") and path.endswith("/role"):
            actor = self.require_role(headers, {"superadmin"})
            user_id = path.split("/")[-2]
            return json_response(200, {"user": self.update_user_role(actor, user_id, read_json(body))})
        if method == "GET" and path == "/api/audit-logs":
            self.require_role(headers, {"superadmin"})
            return json_response(200, {"logs": self.list_audit_logs(query)})
        raise HTTPError(404, "api not found")

    def serve_static(self, path):
        rel_path = "index.html" if path in ("", "/") else path.lstrip("/")
        if rel_path.startswith("uploads/"):
            upload_candidate = (self.upload_dir / rel_path.removeprefix("uploads/")).resolve()
            upload_root = self.upload_dir.resolve()
            try:
                upload_candidate.relative_to(upload_root)
            except ValueError:
                raise HTTPError(404, "file not found")
            if upload_candidate.is_file():
                content_type = mimetypes.guess_type(str(upload_candidate))[0] or "application/octet-stream"
                return 200, {"Content-Type": content_type}, upload_candidate.read_bytes()
        candidate = (APP_ROOT / rel_path).resolve()
        if not str(candidate).startswith(str(APP_ROOT)) or not candidate.is_file():
            raise HTTPError(404, "file not found")
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        return 200, {"Content-Type": content_type}, candidate.read_bytes()

    def login(self, payload):
        username = text(payload.get("username") or payload.get("email"))
        password = str(payload.get("password") or "")
        with self.connect() as conn:
            user = conn.execute(
                "select * from users where username = ? or email = ?",
                (username, normalize_email(username)),
            ).fetchone()
            if user is None or not verify_password(password, user["password_hash"]):
                raise HTTPError(401, "用户名或密码错误")
            token = secrets.token_urlsafe(32)
            conn.execute(
                "insert into sessions(token_hash, user_id, expires_at, created_at) values(?,?,?,?)",
                (hash_token(token), user["id"], int(time.time()) + 86400 * 14, now_iso()),
            )
        headers = {"Set-Cookie": cookie_header(token)}
        return json_response(200, {"user": public_user(user)}, headers)

    def send_verification_code(self, purpose, payload, require_existing=False):
        email = normalize_email(payload.get("email"))
        if not is_valid_email(email):
            raise HTTPError(400, "邮箱格式不正确")
        with self.connect() as conn:
            existing = conn.execute("select id from users where email = ?", (email,)).fetchone()
            if require_existing and existing is None:
                raise HTTPError(404, "邮箱未注册")
            if purpose == "register" and existing is not None:
                raise HTTPError(409, "邮箱已注册")
            now = int(time.time())
            record = conn.execute(
                "select cooldown_until from verification_codes where purpose = ? and email = ?",
                (purpose, email),
            ).fetchone()
            if record and now < int(record["cooldown_until"]):
                raise HTTPError(429, "验证码发送太频繁")
            code = f"{secrets.randbelow(1000000):06d}"
            expires_at = now + self.register_code_ttl
            conn.execute(
                """
                insert into verification_codes(purpose, email, code_hash, expires_at, cooldown_until, created_at)
                values(?,?,?,?,?,?)
                on conflict(purpose, email) do update set
                  code_hash = excluded.code_hash,
                  expires_at = excluded.expires_at,
                  cooldown_until = excluded.cooldown_until,
                  created_at = excluded.created_at
                """,
                (purpose, email, hash_code(code), expires_at, now + self.register_code_cooldown, now_iso()),
            )
        self.mailer.send_register_code(email, code, expires_at)
        return json_response(
            200,
            {
                "email": email,
                "cooldownSeconds": self.register_code_cooldown,
                "expiresInSeconds": self.register_code_ttl,
                "message": "验证码已发送，请检查邮箱",
            },
        )

    def verify_code(self, purpose, email, code):
        code = text(code)
        if len(code) != 6 or not code.isdigit():
            raise HTTPError(400, "验证码必须是 6 位数字")
        with self.connect() as conn:
            record = conn.execute(
                "select code_hash, expires_at from verification_codes where purpose = ? and email = ?",
                (purpose, email),
            ).fetchone()
            if record is None or not hmac.compare_digest(record["code_hash"], hash_code(code)):
                raise HTTPError(400, "验证码错误")
            if int(time.time()) > int(record["expires_at"]):
                conn.execute("delete from verification_codes where purpose = ? and email = ?", (purpose, email))
                raise HTTPError(400, "验证码已过期")
            conn.execute("delete from verification_codes where purpose = ? and email = ?", (purpose, email))

    def register(self, payload):
        email = normalize_email(payload.get("email"))
        username = normalize_username(payload.get("username")) or email
        password = str(payload.get("password") or "")
        nickname = text(payload.get("nickname")) or username
        avatar_url = self.avatar_url_from_payload(payload)
        if not is_valid_email(email) or len(password) < 8:
            raise HTTPError(400, "注册信息不完整")
        self.verify_code("register", email, payload.get("verificationCode"))
        invite_code = text(payload.get("inviteCode"))
        with self.connect() as conn:
            inviter = None
            if invite_code:
                inviter = conn.execute("select id from users where invite_code = ?", (invite_code,)).fetchone()
                if inviter is None:
                    raise HTTPError(400, "邀请码无效")
            try:
                conn.execute(
                    """
                    insert into users(username, email, password_hash, role, nickname, avatar_url, invite_code, invited_by, created_at)
                    values(?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        username,
                        email,
                        hash_password(password),
                        "member",
                        nickname,
                        avatar_url,
                        generate_invite_code(),
                        inviter["id"] if inviter else None,
                        now_iso(),
                    ),
                )
            except sqlite3.IntegrityError:
                raise HTTPError(409, "邮箱已注册")
            user = conn.execute(
                """
                select users.*, inviter.username as invited_by_username
                from users left join users inviter on inviter.id = users.invited_by
                where users.email = ?
                """,
                (email,),
            ).fetchone()
            self.write_audit_log(
                conn,
                None,
                "user.register",
                "user",
                str(user["id"]),
                {"email": email, "invitedBy": inviter["id"] if inviter else None},
            )
        return self.issue_session_response(user, 201)

    def reset_password(self, payload):
        email = normalize_email(payload.get("email"))
        password = str(payload.get("password") or "")
        if not is_valid_email(email) or len(password) < 8:
            raise HTTPError(400, "重置信息不完整")
        self.verify_code("password-reset", email, payload.get("verificationCode"))
        with self.connect() as conn:
            user = conn.execute("select * from users where email = ?", (email,)).fetchone()
            if user is None:
                raise HTTPError(404, "邮箱未注册")
            conn.execute("update users set password_hash = ? where id = ?", (hash_password(password), user["id"]))
            self.write_audit_log(conn, user, "user.password.reset", "user", str(user["id"]), {"email": email})
        return json_response(200, {"ok": True})

    def update_profile(self, user, payload):
        nickname = text(payload.get("nickname")) or user["nickname"] or user["username"]
        avatar_url = self.avatar_url_from_payload(payload) or user["avatar_url"]
        with self.connect() as conn:
            conn.execute(
                "update users set nickname = ?, avatar_url = ? where id = ?",
                (nickname, avatar_url, user["id"]),
            )
            updated = conn.execute("select * from users where id = ?", (user["id"],)).fetchone()
            self.write_audit_log(conn, user, "user.profile.update", "user", str(user["id"]), {"nickname": nickname})
        return public_user(updated)

    def avatar_url_from_payload(self, payload):
        image = text(payload.get("avatarImage"))
        if image:
            return self.save_avatar_image(image)
        return text(payload.get("avatarUrl"))

    def save_avatar_image(self, data_url):
        if "," not in data_url:
            raise HTTPError(400, "头像图片格式不正确")
        header, encoded = data_url.split(",", 1)
        content_types = {
            "data:image/png;base64": ".png",
            "data:image/jpeg;base64": ".jpg",
            "data:image/jpg;base64": ".jpg",
            "data:image/webp;base64": ".webp",
        }
        extension = content_types.get(header.lower())
        if extension is None:
            raise HTTPError(400, "仅支持 png、jpg、webp 头像")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPError(400, "头像图片格式不正确")
        if len(raw) > 2 * 1024 * 1024:
            raise HTTPError(400, "头像图片不能超过 2MB")
        avatar_dir = self.upload_dir / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)
        filename = secrets.token_urlsafe(16) + extension
        path = avatar_dir / filename
        path.write_bytes(raw)
        return f"/uploads/avatars/{filename}"

    def issue_session_response(self, user, status):
        token = secrets.token_urlsafe(32)
        with self.connect() as conn:
            conn.execute(
                "insert into sessions(token_hash, user_id, expires_at, created_at) values(?,?,?,?)",
                (hash_token(token), user["id"], int(time.time()) + 86400 * 14, now_iso()),
            )
        return json_response(status, {"user": public_user(user)}, {"Set-Cookie": cookie_header(token)})

    def logout(self, headers, _user):
        token = get_cookie(headers, "stockrail_session")
        if not token:
            return
        with self.connect() as conn:
            conn.execute("delete from sessions where token_hash = ?", (hash_token(token),))

    def require_user(self, headers):
        token = get_cookie(headers, "stockrail_session")
        if not token:
            raise HTTPError(401, "请先登录")
        with self.connect() as conn:
            row = conn.execute(
                """
                select users.* from sessions
                join users on users.id = sessions.user_id
                where sessions.token_hash = ? and sessions.expires_at > ?
                """,
                (hash_token(token), int(time.time())),
            ).fetchone()
        if row is None:
            raise HTTPError(401, "登录已失效")
        return row

    def require_role(self, headers, roles):
        user = self.require_user(headers)
        if user["role"] not in roles:
            raise HTTPError(403, "权限不足")
        return user

    def create_user(self, actor, payload):
        requested_username = normalize_username(payload.get("username"))
        email = normalize_email(payload.get("email"))
        if not email and is_valid_email(requested_username):
            email = requested_username
        if not email and requested_username:
            email = f"{requested_username}@stockrail.local"
        username = normalize_username(payload.get("username")) or email
        password = str(payload.get("password") or "")
        role = text(payload.get("role"))
        if not username or not is_valid_email(email) or len(password) < 8 or role not in ROLES:
            raise HTTPError(400, "用户信息不完整")
        with self.connect() as conn:
            try:
                conn.execute(
                    "insert into users(username, email, password_hash, role, nickname, invite_code, created_at) values(?,?,?,?,?,?,?)",
                    (username, email, hash_password(password), role, username, generate_invite_code(), now_iso()),
                )
            except sqlite3.IntegrityError:
                raise HTTPError(409, "邮箱已注册")
            user = conn.execute("select * from users where username = ?", (username,)).fetchone()
            self.write_audit_log(conn, actor, "user.create", "user", str(user["id"]), {"email": email, "role": role})
        return public_user(user)

    def list_users(self):
        with self.connect() as conn:
            users = conn.execute("select id, username, email, nickname, role, created_at from users order by id asc").fetchall()
        return [dict(user) for user in users]

    def update_user_role(self, actor, user_id, payload):
        role = text(payload.get("role"))
        if role not in ROLES:
            raise HTTPError(400, "角色不合法")
        with self.connect() as conn:
            before = conn.execute("select role from users where id = ?", (user_id,)).fetchone()
            conn.execute("update users set role = ? where id = ?", (role, user_id))
            if conn.total_changes == 0:
                raise HTTPError(404, "用户不存在")
            user = conn.execute("select * from users where id = ?", (user_id,)).fetchone()
            self.write_audit_log(
                conn,
                actor,
                "user.role.update",
                "user",
                str(user_id),
                {"from": before["role"] if before else "", "to": role, "email": user["email"]},
            )
        return public_user(user)

    def get_invite_info(self, user, headers):
        with self.connect() as conn:
            invited = conn.execute(
                "select id, username, email, nickname, role, created_at from users where invited_by = ? order by id desc",
                (user["id"],),
            ).fetchall()
        origin = request_origin(headers)
        invite_link = f"{origin}/login.html?invite={user['invite_code']}" if origin else f"/login.html?invite={user['invite_code']}"
        return {
            "inviteCode": user["invite_code"],
            "inviteLink": invite_link,
            "inviteCount": len(invited),
            "invitedUsers": [dict(row) for row in invited],
        }

    def list_audit_logs(self, query):
        try:
            limit = int(query.get("limit", 100))
        except (TypeError, ValueError):
            limit = 100
        limit = min(max(limit, 1), 300)
        with self.connect() as conn:
            rows = conn.execute(
                """
                select id, actor_user_id, actor_email, actor_role, action, target_type, target_id, details_json, created_at
                from audit_logs
                order by id desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [serialize_audit_log(row) for row in rows]

    def write_audit_log(self, conn, actor, action, target_type="", target_id="", details=None):
        details = details or {}
        conn.execute(
            """
            insert into audit_logs(actor_user_id, actor_email, actor_role, action, target_type, target_id, details_json, created_at)
            values(?,?,?,?,?,?,?,?)
            """,
            (
                row_value(actor, "id", None) if actor is not None else None,
                row_value(actor, "email", "") if actor is not None else "",
                row_value(actor, "role", "") if actor is not None else "",
                action,
                target_type,
                str(target_id),
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                now_iso(),
            ),
        )

    def create_order(self, user, payload):
        errors = validate_order(payload)
        if errors:
            raise HTTPError(400, "订单信息不完整", errors)
        order_id = "order-" + secrets.token_hex(8)
        created_at = now_iso()
        items = payload.get("items") or []
        with self.connect() as conn:
            conn.execute(
                """
                insert into orders(id, user_id, status, wechat_name, delivery_method, tracking_numbers,
                  total_boxes, total_cans, phone, remark, created_at)
                values(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    order_id,
                    user["id"],
                    "待处理",
                    text(payload.get("wechatName")),
                    text(payload.get("deliveryMethod")) or "快递/物流",
                    text(payload.get("trackingNumbers")),
                    int(payload.get("totalBoxes")),
                    int(payload.get("totalCans") or 0),
                    text(payload.get("phone")),
                    text(payload.get("remark")),
                    created_at,
                ),
            )
            for item in items:
                conn.execute(
                    "insert into order_items(order_id, brand, product, quantity) values(?,?,?,?)",
                    (order_id, text(item.get("brand")), text(item.get("product")), int(item.get("quantity"))),
                )
            self.write_audit_log(conn, user, "order.create", "order", order_id, {"wechatName": text(payload.get("wechatName"))})
        return self.get_order(user, order_id)

    def list_orders(self, user, filters=None):
        filters = filters or {}
        clauses = []
        params = []
        if user["role"] == "member":
            clauses.append("orders.user_id = ?")
            params.append(user["id"])
        status = text(filters.get("status"))
        if status in {"待处理", "核对中", "已入库"}:
            clauses.append("orders.status = ?")
            params.append(status)
        delivery_method = text(filters.get("deliveryMethod"))
        if delivery_method in {"快递/物流", "自送", "同城配送"}:
            clauses.append("orders.delivery_method = ?")
            params.append(delivery_method)
        keyword = text(filters.get("keyword"))
        if keyword:
            clauses.append(
                "(orders.wechat_name like ? or orders.tracking_numbers like ? or orders.phone like ? or users.username like ?)"
            )
            like = f"%{keyword}%"
            params.extend([like, like, like, like])
        date_from = text(filters.get("dateFrom"))
        if date_from:
            clauses.append("orders.created_at >= ?")
            params.append(date_from + "T00:00:00")
        date_to = text(filters.get("dateTo"))
        if date_to:
            clauses.append("orders.created_at <= ?")
            params.append(date_to + "T23:59:59")
        where = "where " + " and ".join(clauses) if clauses else ""
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                select orders.*, users.username as owner_username
                from orders
                join users on users.id = orders.user_id
                {where}
                order by orders.created_at desc
                """,
                params,
            ).fetchall()
        return [serialize_order_summary(row) for row in rows]

    def get_order(self, user, order_id):
        with self.connect() as conn:
            order = conn.execute(
                """
                select orders.*, users.username as owner_username
                from orders join users on users.id = orders.user_id
                where orders.id = ?
                """,
                (order_id,),
            ).fetchone()
            if order is None:
                raise HTTPError(404, "订单不存在")
            if user["role"] == "member" and order["user_id"] != user["id"]:
                raise HTTPError(403, "权限不足")
            items = conn.execute(
                "select brand, product, quantity from order_items where order_id = ? order by id asc",
                (order_id,),
            ).fetchall()
        return serialize_order(order, items)

    def update_order_status(self, _user, order_id, payload):
        status = text(payload.get("status"))
        if status not in {"待处理", "核对中", "已入库"}:
            raise HTTPError(400, "状态不合法")
        with self.connect() as conn:
            before = conn.execute("select status from orders where id = ?", (order_id,)).fetchone()
            conn.execute("update orders set status = ? where id = ?", (status, order_id))
            if conn.total_changes == 0:
                raise HTTPError(404, "订单不存在")
            self.write_audit_log(
                conn,
                _user,
                "order.status.update",
                "order",
                order_id,
                {"from": before["status"] if before else "", "to": status},
            )
        return self.get_order(_user, order_id)


class HTTPError(Exception):
    def __init__(self, status, message, fields=None):
        self.status = status
        self.message = message
        self.fields = fields or {}


def validate_order(payload):
    errors = {}
    if not text(payload.get("wechatName")):
        errors["wechatName"] = "请填写微信名字"
    if not text(payload.get("trackingNumbers")):
        errors["trackingNumbers"] = "请填写快递单号"
    if not positive_int(payload.get("totalBoxes")):
        errors["totalBoxes"] = "请填写总件数"
    if not text(payload.get("phone")):
        errors["phone"] = "请填写联系方式"
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    if not items:
        errors["items"] = "请至少添加 1 条入库明细"
    for index, item in enumerate(items):
        if not text(item.get("brand")) or not text(item.get("product")) or not positive_int(item.get("quantity")):
            errors["items"] = f"请完善第 {index + 1} 条入库明细"
            break
    return errors


def serialize_order_summary(row):
    return {
        "id": row["id"],
        "ownerUsername": row["owner_username"],
        "status": row["status"],
        "wechatName": row["wechat_name"],
        "deliveryMethod": row["delivery_method"],
        "trackingNumbers": row["tracking_numbers"],
        "totalBoxes": row["total_boxes"],
        "totalCans": row["total_cans"],
        "phone": row["phone"],
        "remark": row["remark"],
        "createdAt": row["created_at"],
    }


def serialize_order(row, items):
    result = serialize_order_summary(row)
    result["items"] = [dict(item) for item in items]
    return result


def serialize_audit_log(row):
    try:
        details = json.loads(row["details_json"] or "{}")
    except json.JSONDecodeError:
        details = {}
    return {
        "id": row["id"],
        "actorUserId": row["actor_user_id"],
        "actorEmail": row["actor_email"],
        "actorRole": row["actor_role"],
        "action": row["action"],
        "targetType": row["target_type"],
        "targetId": row["target_id"],
        "details": details,
        "createdAt": row["created_at"],
    }


def public_user(user):
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "nickname": user["nickname"] or user["username"],
        "avatarUrl": user["avatar_url"],
        "inviteCode": user["invite_code"],
        "invitedByUsername": row_value(user, "invited_by_username", ""),
        "createdAt": user["created_at"],
    }


def ensure_user_column(conn, name, definition):
    columns = {row["name"] for row in conn.execute("pragma table_info(users)").fetchall()}
    if name not in columns:
        conn.execute(f"alter table users add column {name} {definition}")


def read_json(body):
    if not body:
        return {}
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPError(400, "JSON 格式错误")


def json_response(status, payload, extra_headers=None):
    if isinstance(payload, HTTPError):
        payload = {"error": payload.message, "fields": payload.fields}
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if extra_headers:
        headers.update(extra_headers)
    return status, headers, body


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260000)
    return "pbkdf2_sha256$260000$" + b64(salt) + "$" + b64(digest)


def verify_password(password, encoded):
    try:
        algorithm, rounds, salt, digest = encoded.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), b64decode(salt), int(rounds))
    return hmac.compare_digest(candidate, b64decode(digest))


def hash_token(token):
    return hmac.new(b"stockrail-session", token.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_code(code):
    return hmac.new(b"stockrail-verification", code.encode("utf-8"), hashlib.sha256).hexdigest()


def cookie_header(token):
    return f"stockrail_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={86400 * 14}"


def get_cookie(headers, name):
    cookie = headers.get("Cookie") or headers.get("cookie") or ""
    for part in cookie.split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        if key == name:
            return value
    return ""


def b64(value):
    return base64.urlsafe_b64encode(value).decode("ascii")


def b64decode(value):
    return base64.urlsafe_b64decode(value.encode("ascii"))


def text(value):
    return str(value or "").strip()


def normalize_email(value):
    return text(value).lower()


def normalize_username(value):
    return text(value).lower()


def is_valid_email(value):
    email = normalize_email(value)
    parsed_name, parsed_email = parseaddr(email)
    return bool(email and parsed_email == email and "@" in email and "." in email.rsplit("@", 1)[-1])


def row_value(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError):
        return default


def positive_int(value):
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def duration_env(name, default_seconds):
    value = text(os.environ.get(name))
    if not value:
        return default_seconds
    try:
        return int(value)
    except ValueError:
        pass
    units = {"s": 1, "m": 60, "h": 3600}
    suffix = value[-1].lower()
    if suffix in units:
        try:
            return int(value[:-1]) * units[suffix]
        except ValueError:
            return default_seconds
    return default_seconds


def generate_invite_code():
    return secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]


def request_origin(headers):
    host = headers.get("Host") or headers.get("host")
    if not host:
        return ""
    proto = headers.get("X-Forwarded-Proto") or headers.get("x-forwarded-proto") or "http"
    return f"{proto}://{host}"


class SMTPMailer:
    def __init__(self, host, port, username, password, from_addr, allow_log):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.allow_log = allow_log

    @classmethod
    def from_env(cls):
        return cls(
            os.environ.get("SMTP_HOST", ""),
            int(os.environ.get("SMTP_PORT", "587") or "587"),
            os.environ.get("SMTP_USERNAME", ""),
            os.environ.get("SMTP_PASSWORD", ""),
            os.environ.get("SMTP_FROM", os.environ.get("SMTP_USERNAME", "noreply@example.com")),
            os.environ.get("ALLOW_INSECURE_MAIL_LOG", "true").lower() == "true",
        )

    def send_register_code(self, email, code, expires_at):
        if not self.host or not self.from_addr:
            if self.allow_log:
                print(f"[mail] verification code for {email}: {code}, expires at {expires_at}")
                return
            raise HTTPError(500, "邮箱服务未配置")
        message = build_verification_email(email, code, expires_at)
        message["From"] = self.from_addr
        with smtplib.SMTP(self.host, self.port, timeout=15) as smtp:
            smtp.starttls()
            if self.username and self.password:
                smtp.login(self.username, self.password)
            smtp.send_message(message)


def build_verification_email(email, code, expires_at):
    expires_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(expires_at)))
    message = EmailMessage()
    message["To"] = email
    message["Subject"] = "StockRail 邮箱验证码"
    plain = (
        "StockRail 库存轨道\n\n"
        f"您的邮箱验证码是：{code}\n"
        f"有效期至：{expires_text}\n\n"
        "请在页面中输入验证码完成操作。\n"
        "如果不是您本人操作，请忽略这封邮件。"
    )
    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.6;color:#1f2937">
      <div style="max-width:520px;margin:0 auto;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden">
        <div style="background:#1f5eff;color:#fff;padding:20px 24px">
          <div style="font-size:14px;opacity:.9">StockRail 库存轨道</div>
          <div style="font-size:22px;font-weight:700;margin-top:4px">邮箱验证码</div>
        </div>
        <div style="padding:24px">
          <p>您好，请在 StockRail 页面输入下面的验证码：</p>
          <div style="font-size:32px;font-weight:800;letter-spacing:6px;color:#111827;background:#f3f4f6;border-radius:10px;padding:16px;text-align:center">{code}</div>
          <p style="color:#6b7280">有效期至：{expires_text}</p>
          <p style="color:#6b7280">如果不是您本人操作，请忽略这封邮件。</p>
        </div>
      </div>
    </div>
    """
    message.set_content(plain)
    message.add_alternative(html, subtype="html")
    return message


class RequestHandler(BaseHTTPRequestHandler):
    app = None

    def do_GET(self):
        self.respond(*self.app.dispatch("GET", self.path, dict(self.headers), b""))

    def do_POST(self):
        self.respond(*self.app.dispatch("POST", self.path, dict(self.headers), self.read_body()))

    def do_PATCH(self):
        self.respond(*self.app.dispatch("PATCH", self.path, dict(self.headers), self.read_body()))

    def do_DELETE(self):
        self.respond(*self.app.dispatch("DELETE", self.path, dict(self.headers), self.read_body()))

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def respond(self, status, headers, body):
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    app = create_app()
    port = int(os.environ.get("PORT", "4173"))
    RequestHandler.app = app
    server = ThreadingHTTPServer(("127.0.0.1", port), RequestHandler)
    print(f"StockRail listening on 127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
