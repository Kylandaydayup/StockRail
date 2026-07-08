import json
import tempfile
import unittest

from server import create_app


class StockRailServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "db_path": f"{self.tmp.name}/stockrail.db",
                "superadmin_username": "root",
                "superadmin_password": "RootPass123!",
                "session_secret": "test-secret",
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

    def test_public_register_creates_member_with_profile(self):
        response = self.request(
            "POST",
            "/api/register",
            {
                "username": "new-member",
                "password": "MemberPass789!",
                "nickname": "微信昵称A",
                "avatarUrl": "https://example.com/avatar-a.jpg",
            },
        )

        self.assertEqual(response["status"], 201, response)
        self.assertEqual(response["json"]["user"]["role"], "member")
        self.assertEqual(response["json"]["user"]["nickname"], "微信昵称A")
        self.assertEqual(response["json"]["user"]["avatarUrl"], "https://example.com/avatar-a.jpg")
        self.assertIn("Set-Cookie", response["headers"])

    def test_wechat_login_creates_member_from_wechat_profile(self):
        response = self.request(
            "POST",
            "/api/wechat/dev-login",
            {
                "openid": "wechat-openid-1",
                "nickname": "微信小王",
                "avatarUrl": "https://example.com/wechat.jpg",
            },
        )

        self.assertEqual(response["status"], 200, response)
        self.assertEqual(response["json"]["user"]["role"], "member")
        self.assertEqual(response["json"]["user"]["username"], "wechat_wechat-openid-1")
        self.assertEqual(response["json"]["user"]["nickname"], "微信小王")
        self.assertEqual(response["json"]["user"]["avatarUrl"], "https://example.com/wechat.jpg")


if __name__ == "__main__":
    unittest.main()
