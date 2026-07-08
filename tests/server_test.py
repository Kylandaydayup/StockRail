import json
import base64
import tempfile
import unittest

from server import build_verification_email, create_app


class CaptureMailer:
    def __init__(self):
        self.messages = []

    def send_register_code(self, email, code, expires_at):
        self.messages.append({"email": email, "code": code, "expiresAt": expires_at})

    def code_for(self, email):
        for message in reversed(self.messages):
            if message["email"] == email:
                return message["code"]
        return ""


class StockRailServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mailer = CaptureMailer()
        self.app = create_app(
            {
                "db_path": f"{self.tmp.name}/stockrail.db",
                "upload_dir": f"{self.tmp.name}/uploads",
                "superadmin_username": "root",
                "superadmin_email": "root@example.com",
                "superadmin_password": "RootPass123!",
                "session_secret": "test-secret",
                "mailer": self.mailer,
                "register_code_cooldown_seconds": 0,
            }
        )

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, method, path, body=None, cookie=None):
        headers = {}
        if cookie:
            headers["Cookie"] = cookie
        return self.app.handle_test_request(method, path, headers, body)

    def login(self, username, password):
        response = self.request(
            "POST",
            "/api/login",
            {"username": username, "password": password},
        )
        self.assertEqual(response["status"], 200, response)
        return response["headers"]["Set-Cookie"].split(";", 1)[0]

    def create_user(self, cookie, username, password, role):
        response = self.request(
            "POST",
            "/api/users",
            {"username": username, "password": password, "role": role},
            cookie,
        )
        self.assertEqual(response["status"], 201, response)
        return response["json"]

    def register_member(self, email="member@example.com", nickname="用户昵称A", invite_code=""):
        code_response = self.request("POST", "/api/register/code", {"email": email})
        self.assertEqual(code_response["status"], 200, code_response)
        response = self.request(
            "POST",
            "/api/register",
            {
                "email": email,
                "password": "MemberPass789!",
                "nickname": nickname,
                "verificationCode": self.mailer.code_for(email),
                "inviteCode": invite_code,
            },
        )
        self.assertEqual(response["status"], 201, response)
        return response

    def test_superadmin_creates_users_and_admin_lists_orders(self):
        root_cookie = self.login("root", "RootPass123!")
        self.create_user(root_cookie, "member-a", "MemberPass123!", "member")
        self.create_user(root_cookie, "admin-a", "AdminPass123!", "admin")

        member_cookie = self.login("member-a", "MemberPass123!")
        create_response = self.request(
            "POST",
            "/api/orders",
            {
                "wechatName": "测试小王",
                "deliveryMethod": "快递/物流",
                "trackingNumbers": "中通1234",
                "totalBoxes": 2,
                "totalCans": 12,
                "phone": "13800138000",
                "remark": "瘪2个",
                "items": [{"brand": "皇家", "product": "皇家A2", "quantity": 12}],
            },
            member_cookie,
        )
        self.assertEqual(create_response["status"], 201, create_response)

        admin_cookie = self.login("admin-a", "AdminPass123!")
        list_response = self.request("GET", "/api/orders", cookie=admin_cookie)

        self.assertEqual(list_response["status"], 200, list_response)
        self.assertEqual(len(list_response["json"]["orders"]), 1)
        self.assertEqual(list_response["json"]["orders"][0]["wechatName"], "测试小王")

    def test_member_only_reads_own_orders(self):
        root_cookie = self.login("root", "RootPass123!")
        self.create_user(root_cookie, "member-a", "MemberPass123!", "member")
        self.create_user(root_cookie, "member-b", "MemberPass456!", "member")

        member_a = self.login("member-a", "MemberPass123!")
        member_b = self.login("member-b", "MemberPass456!")
        self.request(
            "POST",
            "/api/orders",
            {
                "wechatName": "A",
                "deliveryMethod": "快递/物流",
                "trackingNumbers": "A123",
                "totalBoxes": 1,
                "phone": "13800138000",
                "items": [{"brand": "皇家", "product": "皇家A2", "quantity": 1}],
            },
            member_a,
        )

        response = self.request("GET", "/api/orders", cookie=member_b)

        self.assertEqual(response["status"], 200, response)
        self.assertEqual(response["json"]["orders"], [])

    def test_admin_cannot_manage_users(self):
        root_cookie = self.login("root", "RootPass123!")
        self.create_user(root_cookie, "admin-a", "AdminPass123!", "admin")
        admin_cookie = self.login("admin-a", "AdminPass123!")

        response = self.request(
            "POST",
            "/api/users",
            {"username": "blocked", "password": "Blocked123!", "role": "member"},
            admin_cookie,
        )

        self.assertEqual(response["status"], 403, response)

    def test_public_register_requires_email_verification_and_supports_email_login(self):
        missing_code = self.request(
            "POST",
            "/api/register",
            {
                "email": "new-member@example.com",
                "password": "MemberPass789!",
                "nickname": "用户昵称A",
                "avatarUrl": "https://example.com/avatar-a.jpg",
            },
        )
        self.assertEqual(missing_code["status"], 400, missing_code)

        response = self.register_member("new-member@example.com", "用户昵称A")

        self.assertEqual(response["json"]["user"]["role"], "member")
        self.assertEqual(response["json"]["user"]["email"], "new-member@example.com")
        self.assertEqual(response["json"]["user"]["nickname"], "用户昵称A")
        self.assertIn("Set-Cookie", response["headers"])
        login_cookie = self.login("new-member@example.com", "MemberPass789!")
        self.assertTrue(login_cookie.startswith("stockrail_session="))

    def test_register_and_profile_avatar_upload_save_replaceable_image(self):
        image = "data:image/png;base64," + base64.b64encode(b"first-avatar").decode("ascii")
        email = "avatar-member@example.com"
        self.request("POST", "/api/register/code", {"email": email})
        response = self.request(
            "POST",
            "/api/register",
            {
                "email": email,
                "password": "MemberPass789!",
                "nickname": "头像用户",
                "verificationCode": self.mailer.code_for(email),
                "avatarImage": image,
            },
        )

        self.assertEqual(response["status"], 201, response)
        first_url = response["json"]["user"]["avatarUrl"]
        self.assertTrue(first_url.startswith("/uploads/avatars/"), first_url)
        with open(f"{self.tmp.name}{first_url}", "rb") as saved:
            self.assertEqual(saved.read(), b"first-avatar")

        cookie = response["headers"]["Set-Cookie"].split(";", 1)[0]
        replacement = "data:image/jpeg;base64," + base64.b64encode(b"replacement-avatar").decode("ascii")
        update = self.request(
            "PATCH",
            "/api/me/profile",
            {"nickname": "新头像用户", "avatarImage": replacement},
            cookie,
        )

        self.assertEqual(update["status"], 200, update)
        self.assertEqual(update["json"]["user"]["nickname"], "新头像用户")
        replacement_url = update["json"]["user"]["avatarUrl"]
        self.assertTrue(replacement_url.endswith(".jpg"), replacement_url)
        with open(f"{self.tmp.name}{replacement_url}", "rb") as saved:
            self.assertEqual(saved.read(), b"replacement-avatar")

    def test_invite_link_records_inviter_and_invited_members(self):
        inviter = self.register_member("inviter@example.com", "邀请人")
        inviter_cookie = inviter["headers"]["Set-Cookie"].split(";", 1)[0]
        invite = self.request("GET", "/api/invite", cookie=inviter_cookie)
        self.assertEqual(invite["status"], 200, invite)
        self.assertIn("/login.html?invite=", invite["json"]["inviteLink"])

        invite_code = invite["json"]["inviteCode"]
        invited = self.register_member("invited@example.com", "被邀请人", invite_code)

        self.assertEqual(invited["json"]["user"]["invitedByUsername"], "inviter@example.com")
        refreshed = self.request("GET", "/api/invite", cookie=inviter_cookie)
        self.assertEqual(refreshed["json"]["inviteCount"], 1)
        self.assertEqual(refreshed["json"]["invitedUsers"][0]["email"], "invited@example.com")

    def test_superadmin_updates_existing_user_role(self):
        root_cookie = self.login("root", "RootPass123!")
        member = self.register_member("role-target@example.com", "权限用户")
        user_id = member["json"]["user"]["id"]

        response = self.request(
            "PATCH",
            f"/api/users/{user_id}/role",
            {"role": "admin"},
            root_cookie,
        )

        self.assertEqual(response["status"], 200, response)
        self.assertEqual(response["json"]["user"]["role"], "admin")

    def test_password_reset_uses_email_verification_code(self):
        self.register_member("reset@example.com", "重置用户")
        code_response = self.request("POST", "/api/password-reset/code", {"email": "reset@example.com"})
        self.assertEqual(code_response["status"], 200, code_response)

        reset_response = self.request(
            "POST",
            "/api/password-reset",
            {
                "email": "reset@example.com",
                "password": "NewPass123!",
                "verificationCode": self.mailer.code_for("reset@example.com"),
            },
        )

        self.assertEqual(reset_response["status"], 200, reset_response)
        login_cookie = self.login("reset@example.com", "NewPass123!")
        self.assertTrue(login_cookie.startswith("stockrail_session="))

    def test_branded_email_template_contains_stockrail_identity(self):
        message = build_verification_email("buyer@example.com", "123456", 1783522000)

        self.assertEqual(message["Subject"], "StockRail 邮箱验证码")
        rendered = message.get_body(preferencelist=("plain",)).get_content()
        self.assertIn("StockRail 库存轨道", rendered)
        self.assertIn("123456", rendered)
        self.assertIn("不是您本人操作", rendered)

    def test_superadmin_views_immutable_audit_logs_for_important_operations(self):
        root_cookie = self.login("root", "RootPass123!")
        member = self.register_member("audit-target@example.com", "审计用户")
        user_id = member["json"]["user"]["id"]
        role_response = self.request("PATCH", f"/api/users/{user_id}/role", {"role": "admin"}, root_cookie)
        self.assertEqual(role_response["status"], 200, role_response)

        logs_response = self.request("GET", "/api/audit-logs", cookie=root_cookie)
        self.assertEqual(logs_response["status"], 200, logs_response)
        actions = [log["action"] for log in logs_response["json"]["logs"]]
        self.assertIn("user.register", actions)
        self.assertIn("user.role.update", actions)

        admin_cookie = self.login("audit-target@example.com", "MemberPass789!")
        blocked = self.request("GET", "/api/audit-logs", cookie=admin_cookie)
        self.assertEqual(blocked["status"], 403, blocked)

        delete_attempt = self.request("DELETE", "/api/audit-logs/1", cookie=root_cookie)
        self.assertEqual(delete_attempt["status"], 404, delete_attempt)

    def test_admin_filters_orders_by_status_delivery_and_keyword(self):
        root_cookie = self.login("root", "RootPass123!")
        self.create_user(root_cookie, "member-a", "MemberPass123!", "member")
        self.create_user(root_cookie, "admin-a", "AdminPass123!", "admin")
        member_cookie = self.login("member-a", "MemberPass123!")
        admin_cookie = self.login("admin-a", "AdminPass123!")

        first = self.request(
            "POST",
            "/api/orders",
            {
                "wechatName": "筛选目标",
                "deliveryMethod": "自送",
                "trackingNumbers": "TARGET-001",
                "totalBoxes": 3,
                "phone": "13900001111",
                "items": [{"brand": "皇家", "product": "皇家A2", "quantity": 3}],
            },
            member_cookie,
        )
        second = self.request(
            "POST",
            "/api/orders",
            {
                "wechatName": "普通订单",
                "deliveryMethod": "快递/物流",
                "trackingNumbers": "OTHER-002",
                "totalBoxes": 1,
                "phone": "13900002222",
                "items": [{"brand": "爱他美", "product": "卓萃", "quantity": 1}],
            },
            member_cookie,
        )
        self.assertEqual(first["status"], 201, first)
        self.assertEqual(second["status"], 201, second)
        self.request("PATCH", f"/api/orders/{first['json']['order']['id']}/status", {"status": "核对中"}, admin_cookie)

        response = self.request(
            "GET",
            "/api/orders?status=%E6%A0%B8%E5%AF%B9%E4%B8%AD&deliveryMethod=%E8%87%AA%E9%80%81&keyword=TARGET",
            cookie=admin_cookie,
        )

        self.assertEqual(response["status"], 200, response)
        self.assertEqual([order["wechatName"] for order in response["json"]["orders"]], ["筛选目标"])

    def test_wechat_login_endpoint_is_removed(self):
        response = self.request(
            "POST",
            "/api/wechat/dev-login",
            {
                "openid": "wechat-openid-1",
                "nickname": "微信小王",
                "avatarUrl": "https://example.com/wechat.jpg",
            },
        )

        self.assertEqual(response["status"], 404, response)


if __name__ == "__main__":
    unittest.main()
