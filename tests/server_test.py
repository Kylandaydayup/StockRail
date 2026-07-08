import json
import base64
import tempfile
import unittest

from server import create_app


class StockRailServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "db_path": f"{self.tmp.name}/stockrail.db",
                "upload_dir": f"{self.tmp.name}/uploads",
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
                "nickname": "用户昵称A",
                "avatarUrl": "https://example.com/avatar-a.jpg",
            },
        )

        self.assertEqual(response["status"], 201, response)
        self.assertEqual(response["json"]["user"]["role"], "member")
        self.assertEqual(response["json"]["user"]["nickname"], "用户昵称A")
        self.assertEqual(response["json"]["user"]["avatarUrl"], "https://example.com/avatar-a.jpg")
        self.assertIn("Set-Cookie", response["headers"])

    def test_register_and_profile_avatar_upload_save_replaceable_image(self):
        image = "data:image/png;base64," + base64.b64encode(b"first-avatar").decode("ascii")
        response = self.request(
            "POST",
            "/api/register",
            {
                "username": "avatar-member",
                "password": "MemberPass789!",
                "nickname": "头像用户",
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
