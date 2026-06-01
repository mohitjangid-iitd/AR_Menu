"""
tests/test_smoke.py — Smoke Tests

Sirf ye check karo: kya API zinda hai?
200/302/401/403 — sab acceptable hain.
500 = problem hai.

Run: pytest tests/test_smoke.py -v
"""

import pytest


# ════════════════════════════════
# PUBLIC ROUTES — No auth needed
# ════════════════════════════════

class TestPublicRoutes:
    """Koi bhi access kar sake"""

    def test_ping(self, client):
        r = client.get("/ping")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_landing_page(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_sitemap(self, client):
        r = client.get("/sitemap.xml")
        assert r.status_code == 200
        assert "xml" in r.headers.get("content-type", "")

    def test_google_verification(self, client):
        """Google Search Console verification file"""
        r = client.get("/google67ff8e4e4bb9c2ef.html")
        # 200 ya 404 dono ok — file exist kare toh 200
        assert r.status_code in (200, 404)

    def test_unknown_route_not_500(self, client):
        """Random route 500 nahi deni chahiye"""
        r = client.get("/this-route-does-not-exist-xyz")
        assert r.status_code != 500


# ════════════════════════════════
# AUTH ROUTES
# ════════════════════════════════

class TestAuthRoutes:
    """Login/logout endpoints"""

    def test_login_page_loads(self, client):
        r = client.get("/test_resto/login")
        assert r.status_code in (200, 404)  # 404 agar client_id check ho

    def test_login_wrong_credentials(self, client):
        """Wrong password — 401 ya redirect, kabhi 500 nahi"""
        r = client.post("/api/login", json={
            "client_id": "test_resto",
            "username":  "wrong_user",
            "password":  "wrong_pass",
            "role":      "owner",
        }, follow_redirects=False)
        assert r.status_code not in (500,)

    def test_admin_login_page(self, client):
        r = client.get("/admin/login")
        assert r.status_code in (200, 404)


# ════════════════════════════════
# OWNER ROUTES — Auth required
# ════════════════════════════════

class TestOwnerRoutes:
    """Owner dashboard APIs — token chahiye"""

    def test_owner_dashboard_no_auth(self, client):
        """Bina token ke 401/403/redirect milna chahiye, 500 nahi"""
        r = client.get("/test_resto/staff/owner", follow_redirects=False)
        assert r.status_code not in (500,)

    def test_owner_dashboard_with_auth(self, owner_client):
        r = owner_client.get("/test_resto/staff/owner", follow_redirects=False)
        assert r.status_code not in (500,)

    def test_menu_api(self, owner_client):
        r = owner_client.get("/api/menu/test_resto")
        assert r.status_code not in (500,)

    def test_orders_api(self, owner_client):
        r = owner_client.get("/api/orders/test_resto")
        assert r.status_code not in (500,)

    def test_tables_api(self, owner_client):
        r = owner_client.get("/api/tables/test_resto")
        assert r.status_code not in (500,)


# ════════════════════════════════
# BILLING ROUTES — Admin required
# ════════════════════════════════

class TestBillingRoutes:
    """Billing APIs — admin token chahiye"""

    def test_plans_no_auth(self, client):
        """Bina auth ke 403 milna chahiye"""
        r = client.get("/api/billing/plans")
        assert r.status_code == 403

    def test_plans_with_admin(self, admin_client):
        r = admin_client.get("/api/billing/plans")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_addons_with_admin(self, admin_client):
        r = admin_client.get("/api/billing/addons")
        assert r.status_code == 200

    def test_subscriptions_list(self, admin_client):
        r = admin_client.get("/api/billing/subscriptions")
        assert r.status_code == 200
        data = r.json()
        assert "subscriptions" in data
        assert "plans" in data

    def test_subscription_detail(self, admin_client):
        r = admin_client.get("/api/billing/subscriptions/test_resto")
        assert r.status_code == 200
        data = r.json()
        assert "subscription" in data

    def test_price_preview(self, admin_client):
        r = admin_client.get(
            "/api/billing/preview-price",
            params={"plan_key": "pro", "period": "monthly"}
        )
        assert r.status_code == 200
        data = r.json()
        assert "grand_total" in data

    def test_features_me_no_auth(self, client):
        """Bina auth ke 401 milna chahiye"""
        r = client.get("/api/billing/features/me")
        assert r.status_code in (401, 403)

    def test_features_me_with_owner(self, owner_client):
        r = owner_client.get("/api/billing/features/me")
        assert r.status_code == 200
        data = r.json()
        assert "features" in data
        assert "client_id" in data


# ════════════════════════════════
# BLOG ROUTES
# ════════════════════════════════

class TestBlogRoutes:

    def test_blog_list_public(self, client):
        r = client.get("/blog")
        assert r.status_code in (200, 404)

    def test_blog_editor_no_auth(self, client):
        """Editor bina auth ke accessible nahi hona chahiye"""
        r = client.get("/blog/editor", follow_redirects=False)
        assert r.status_code not in (200, 500)


# ════════════════════════════════
# STAFF ROUTES
# ════════════════════════════════

class TestStaffRoutes:

    def test_kitchen_no_auth(self, client):
        r = client.get("/test_resto/staff/kitchen", follow_redirects=False)
        assert r.status_code not in (500,)

    def test_waiter_no_auth(self, client):
        r = client.get("/test_resto/staff/waiter", follow_redirects=False)
        assert r.status_code not in (500,)

    def test_counter_no_auth(self, client):
        r = client.get("/test_resto/staff/counter", follow_redirects=False)
        assert r.status_code not in (500,)

    def test_delivery_no_auth(self, client):
        r = client.get("/test_resto/staff/delivery", follow_redirects=False)
        assert r.status_code not in (500,)

    def test_delivery_with_auth_feature_disabled_fails_403(self, owner_client):
        """Delivery dashboard should fail with 403 when delivery feature is disabled"""
        r = owner_client.get("/test_resto/staff/delivery", follow_redirects=False)
        assert r.status_code == 403

    def test_delivery_with_auth_feature_enabled_succeeds_200(self, owner_client):
        """Delivery dashboard should succeed with 200 when delivery feature is enabled"""
        from unittest.mock import patch
        with patch("helpers.has_feature", return_value=True):
            r = owner_client.get("/test_resto/staff/delivery", follow_redirects=False)
        assert r.status_code == 200


# ════════════════════════════════
# CHATBOT ROUTES
# ════════════════════════════════

class TestChatbotRoutes:

    def test_chatbot_no_auth(self, client):
        r = client.post("/api/chatbot/test_resto", json={"message": "hello"})
        assert r.status_code not in (500,)

    def test_help_chat(self, client):
        r = client.post("/api/help-chat", json={"message": "help"})
        assert r.status_code not in (500,)
