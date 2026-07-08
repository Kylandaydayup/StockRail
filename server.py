#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import sqlite3
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


APP_ROOT = Path(__file__).resolve().parent
ROLES = {"member", "admin", "superadmin"}


def create_app(config=None):
    config = config or {}
    db_path = config.get("db_path") or os.environ.get("STOCKRAIL_DB", str(APP_ROOT / "data" / "stockrail.db"))
    app = StockRailApp(
        db_path=db_path,
        session_secret=config.get("session_secret") or os.environ.get("STOCKRAIL_SESSION_SECRET", "dev-session-secret"),
        superadmin_username=config.get("superadmin_username") or os.environ.get("STOCKRAIL_SUPERADMIN_USER", "superadmin"),
        superadmin_password=config.get("superadmin_password") or os.environ.get("STOCKRAIL_SUPERADMIN_PASSWORD", "ChangeMe123!"),
    )
    app.init_db()
    return app


class StockRailApp:
    def __init__(self, db_path, session_secret, superadmin_username, superadmin_password):
        self.db_path = db_path
        self.session_secret = session_secret.encode("utf-8")
        self.superadmin_username = superadmin_username
        self.superadmin_password = superadmin_password

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
                  password_hash text not null,
                  role text not null check(role in ('member','admin','superadmin')),
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
                """
            )
            user = conn.execute("select id from users where username = ?", (self.superadmin_username,)).fetchone()
            if user is None:
                conn.execute(
                    "insert into users(username, password_hash, role, created_at) values(?,?,?,?)",
                    (self.superadmin_username, hash_password(self.superadmin_password), "superadmin", now_iso()),
                )

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
        path = urlparse(raw_path).path
        try:
            if path.startswith("/api/"):
                return self.dispatch_api(method, path, headers, body)
            return self.serve_static(path)
        except HTTPError as exc:
            return json_response(exc.status, {"error": exc.message})
        except Exception as exc:
            return json_response(500, {"error": "internal server error", "detail": str(exc)})

    def dispatch_api(self, method, path, headers, body):
        if method == "POST" and path == "/api/login":
            return self.login(read_json(body))
        if method == "POST" and path == "/api/logout":
            user = self.require_user(headers)
            self.logout(headers, user)
            return json_response(200, {"ok": True})
        if method == "GET" and path == "/api/me":
            user = self.require_user(headers)
            return json_response(200, {"user": public_user(user)})
        if method == "GET" and path == "/api/orders":
            user = self.require_user(headers)
            return json_response(200, {"orders": self.list_orders(user)})
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
            self.require_role(headers, {"superadmin"})
            return json_response(201, {"user": self.create_user(read_json(body))})
        raise HTTPError(404, "api not found")

    def serve_static(self, path):
        rel_path = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (APP_ROOT / rel_path).resolve()
        if not str(candidate).startswith(str(APP_ROOT)) or not candidate.is_file():
            raise HTTPError(404, "file not found")
        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        return 200, {"Content-Type": content_type}, candidate.read_bytes()

    def login(self, payload):
        username = text(payload.get("username"))
        password = str(payload.get("password") or "")
        with self.connect() as conn:
            user = conn.execute("select * from users where username = ?", (username,)).fetchone()
            if user is None or not verify_password(password, user["password_hash"]):
                raise HTTPError(401, "用户名或密码错误")
            token = secrets.token_urlsafe(32)
            conn.execute(
                "insert into sessions(token_hash, user_id, expires_at, created_at) values(?,?,?,?)",
                (hash_token(token), user["id"], int(time.time()) + 86400 * 14, now_iso()),
            )
        headers = {"Set-Cookie": cookie_header(token)}
        return json_response(200, {"user": public_user(user)}, headers)

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

    def create_user(self, payload):
        username = text(payload.get("username"))
        password = str(payload.get("password") or "")
        role = text(payload.get("role"))
        if not username or len(password) < 8 or role not in ROLES:
            raise HTTPError(400, "用户信息不完整")
        with self.connect() as conn:
            try:
                conn.execute(
                    "insert into users(username, password_hash, role, created_at) values(?,?,?,?)",
                    (username, hash_password(password), role, now_iso()),
                )
            except sqlite3.IntegrityError:
                raise HTTPError(409, "用户名已存在")
            user = conn.execute("select * from users where username = ?", (username,)).fetchone()
        return public_user(user)

    def list_users(self):
        with self.connect() as conn:
            users = conn.execute("select id, username, role, created_at from users order by id asc").fetchall()
        return [dict(user) for user in users]

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
        return self.get_order(user, order_id)

    def list_orders(self, user):
        where = ""
        params = []
        if user["role"] == "member":
            where = "where orders.user_id = ?"
            params.append(user["id"])
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
            conn.execute("update orders set status = ? where id = ?", (status, order_id))
            if conn.total_changes == 0:
                raise HTTPError(404, "订单不存在")
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


def public_user(user):
    return {"id": user["id"], "username": user["username"], "role": user["role"], "createdAt": user["created_at"]}


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


def positive_int(value):
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class RequestHandler(BaseHTTPRequestHandler):
    app = None

    def do_GET(self):
        self.respond(*self.app.dispatch("GET", self.path, dict(self.headers), b""))

    def do_POST(self):
        self.respond(*self.app.dispatch("POST", self.path, dict(self.headers), self.read_body()))

    def do_PATCH(self):
        self.respond(*self.app.dispatch("PATCH", self.path, dict(self.headers), self.read_body()))

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
