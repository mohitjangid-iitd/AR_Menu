"""
tests/test_admin.py — Admin Router Behavioral Tests

Kya test ho raha hai:
- GET /api/admin/overview       — stats + restaurants
- GET/PUT restaurant JSON       — save, delete
- Staff CRUD via admin          — same as owner but admin role
- Site settings                 — valid/invalid keys
- Non-admin access rejected everywhere
"""

import pytest
from unittest.mock import patch, MagicMock


MOCK_USER_ADMIN = {
    "sub": "admin", "role": "admin",
    "name": "Super Admin", "admin_id": 1,
}

MOCK_RESTAURANTS = [
    {
        "client_id": "spice_garden", "branch_id": "__default__",
        "name": "Spice Garden", "sub_status": "active",
    },
    {
        "client_id": "chai_stop", "branch_id": "__default__",
        "name": "Chai Stop", "sub_status": "trial",
    },
]

MOCK_STATS = {
    "total_restaurants": 2,
    "total_orders": 150,
    "total_revenue": 45000,
}

MOCK_BRANCH = {
    "branch_id": "__default__",
    "theme": None,
    "config": {"restaurant": {"name": "Spice Garden", "num_tables": 8}, "items": []},
}


class TestAdminOverview:
    """GET /api/admin/overview"""

    def test_returns_stats_and_restaurants(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_all_restaurants_info", return_value=MOCK_RESTAURANTS), \
             patch("routers.admin.get_overall_stats", return_value=MOCK_STATS), \
             patch("routers.admin.get_top_dishes_overall", return_value=[]), \
             patch("routers.admin.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.admin.get_restaurant_branches", return_value=[MOCK_BRANCH]):
            r = admin_client.get("/api/admin/overview")
        assert r.status_code == 200
        data = r.json()
        assert "stats" in data
        assert "restaurants" in data

    def test_deduplicates_branches(self, admin_client):
        """Ek hi restaurant ke multiple branches ek row mein aane chahiye"""
        restaurants_with_branches = [
            {"client_id": "spice", "branch_id": "__default__", "sub_status": "active"},
            {"client_id": "spice", "branch_id": "outlet_2",    "sub_status": "active"},
        ]
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_all_restaurants_info", return_value=restaurants_with_branches), \
             patch("routers.admin.get_overall_stats", return_value=MOCK_STATS), \
             patch("routers.admin.get_top_dishes_overall", return_value=[]), \
             patch("routers.admin.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.admin.get_restaurant_branches", return_value=[MOCK_BRANCH]):
            r = admin_client.get("/api/admin/overview")
        # Sirf 1 restaurant hona chahiye, 2 rows nahi
        assert len(r.json()["restaurants"]) == 1

    def test_non_admin_rejected(self, owner_client):
        r = owner_client.get("/api/admin/overview")
        assert r.status_code == 403

    def test_no_auth_rejected(self, client):
        r = client.get("/api/admin/overview")
        assert r.status_code in (302, 403)


class TestAdminRestaurantJson:
    """GET + PUT /api/admin/restaurant/{client_id}/json"""

    def test_get_json_returns_config(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_client_data", return_value=MOCK_BRANCH["config"]):
            r = admin_client.get("/api/admin/restaurant/spice_garden/json")
        assert r.status_code == 200
        assert r.json()["restaurant"]["name"] == "Spice Garden"

    def test_put_json_saves_data(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_restaurant_branches", return_value=[MOCK_BRANCH]), \
             patch("routers.admin.save_restaurant_json") as mock_save, \
             patch("routers.admin.seed_tables"):
            r = admin_client.put("/api/admin/restaurant/spice_garden/json", json={
                "data": {"restaurant": {"name": "Updated Name", "num_tables": 10}, "items": []}
            })
        assert r.status_code == 200
        mock_save.assert_called_once()

    def test_unknown_branch_404(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_client_data", return_value=None):
            r = admin_client.get("/api/admin/restaurant/spice_garden/json?branch_id=no_such_branch")
        assert r.status_code == 404


class TestAdminStaff:
    """Admin staff CRUD — /api/admin/staff/{client_id}"""

    MOCK_STAFF = [
        {"id": 1, "username": "w1", "name": "Waiter 1",
         "role": "waiter", "is_active": True, "branch_id": "__default__"},
    ]

    def test_get_staff_list(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_staff_list", return_value=self.MOCK_STAFF):
            r = admin_client.get("/api/admin/staff/spice_garden")
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_create_staff_success(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.create_staff", return_value=True):
            r = admin_client.post("/api/admin/staff/spice_garden", json={
                "username": "chef_new", "password": "secure",
                "name": "New Chef", "role": "kitchen",
            })
        assert r.status_code == 200

    def test_create_staff_calls_db(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.create_staff", return_value=True) as mock_create:
            admin_client.post("/api/admin/staff/spice_garden", json={
                "username": "w2", "password": "p",
                "name": "Waiter 2", "role": "waiter",
            })
        mock_create.assert_called_once()
        args = mock_create.call_args[0]
        assert args[0] == "spice_garden"
        assert args[4] == "waiter"

    def test_duplicate_staff_409(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.create_staff", return_value=False):
            r = admin_client.post("/api/admin/staff/spice_garden", json={
                "username": "w1", "password": "p",
                "name": "Dup", "role": "waiter",
            })
        assert r.status_code == 409

    def test_update_staff_password(self, admin_client):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"id": 1}
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_db", return_value=mock_conn), \
             patch("routers.admin.update_staff_password") as mock_upd:
            r = admin_client.patch("/api/admin/staff/1/password",
                                   json={"new_password": "newpass"})
        assert r.status_code == 200
        mock_upd.assert_called_once_with(1, "newpass")

    def test_toggle_staff_active(self, admin_client):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"is_active": True}
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_db", return_value=mock_conn), \
             patch("routers.admin.toggle_staff_active") as mock_tog:
            r = admin_client.patch("/api/admin/staff/1/toggle")
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        mock_tog.assert_called_once_with(1, False)

    def test_delete_staff(self, admin_client):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"id": 1}
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_db", return_value=mock_conn), \
             patch("routers.admin.delete_staff") as mock_del:
            r = admin_client.delete("/api/admin/staff/1")
        assert r.status_code == 200
        mock_del.assert_called_once_with(1)


class TestAdminDeleteRestaurant:
    """DELETE /api/admin/restaurant/{client_id}"""

    def test_delete_restaurant_calls_db(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.admin.delete_restaurant_full") as mock_del:
            r = admin_client.delete("/api/admin/restaurant/old_resto")
        assert r.status_code == 200
        mock_del.assert_called_once_with("old_resto")

    def test_delete_unknown_restaurant_404(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_client_data", return_value=None):
            r = admin_client.delete("/api/admin/restaurant/ghost")
        assert r.status_code == 404

    def test_non_admin_cannot_delete(self, owner_client):
        r = owner_client.delete("/api/admin/restaurant/spice_garden")
        assert r.status_code == 403


class TestSiteSettings:
    """PATCH /api/admin/site-settings/{key}"""

    def test_valid_key_updated(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_all_site_settings", return_value={}), \
             patch("routers.admin.set_site_setting") as mock_set:
            r = admin_client.patch(
                "/api/admin/site-settings/chatbot_enabled",
                json={"value": True},
            )
        assert r.status_code == 200
        mock_set.assert_called_once_with("chatbot_enabled", True)

    def test_invalid_key_400(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN):
            r = admin_client.patch(
                "/api/admin/site-settings/delete_all_data",  # ← invalid
                json={"value": True},
            )
        assert r.status_code == 400

    def test_all_valid_keys_accepted(self, admin_client):
        valid_keys = [
            "image_to_menu_enabled", "chatbot_enabled",
            "blog_owner_enabled", "blog_blogger_enabled",
        ]
        for key in valid_keys:
            with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
                 patch("routers.admin.get_all_site_settings", return_value={}), \
                 patch("routers.admin.set_site_setting"):
                r = admin_client.patch(
                    f"/api/admin/site-settings/{key}",
                    json={"value": True},
                )
            assert r.status_code == 200, f"{key} valid key reject hua"

    def test_non_admin_cannot_change_settings(self, owner_client):
        r = owner_client.patch(
            "/api/admin/site-settings/chatbot_enabled",
            json={"value": False},
        )
        assert r.status_code == 403


class TestAdminOwnerManagement:
    """GET/PATCH /api/admin/owner/{client_id}"""

    def test_get_owner_success(self, admin_client):
        mock_owner = {"id": 1, "name": "Ramesh", "client_id": "spice_garden"}
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_owner_by_client_id", return_value=mock_owner):
            r = admin_client.get("/api/admin/owner/spice_garden")
        assert r.status_code == 200
        assert r.json()["name"] == "Ramesh"

    def test_get_owner_not_found_404(self, admin_client):
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_owner_by_client_id", return_value=None):
            r = admin_client.get("/api/admin/owner/ghost_resto")
        assert r.status_code == 404

    def test_toggle_owner_flips_state(self, admin_client):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"is_active": True}
        with patch("routers.admin.require_auth", return_value=MOCK_USER_ADMIN), \
             patch("routers.admin.get_db", return_value=mock_conn), \
             patch("routers.admin.toggle_owner_active") as mock_tog:
            r = admin_client.patch("/api/admin/owner/1/toggle")
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        mock_tog.assert_called_once_with(1, False)
