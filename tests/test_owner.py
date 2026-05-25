"""
tests/test_owner.py — Owner Router Behavioral Tests

Kya test ho raha hai:
- GET /api/owner/{client_id}/json    — config fetch, branch check
- PUT /api/owner/{client_id}/json    — config save, theme preserved
- GET /api/staff/{client_id}         — staff list
- POST /api/staff/{client_id}        — staff create, duplicate check
- PATCH .../password                 — password update
- PATCH .../toggle                   — activate/deactivate
- DELETE .../staff                   — staff delete
- Auth checks across all routes
- Invalid role rejection
"""

import pytest
from unittest.mock import patch, MagicMock, call


MOCK_BRANCH_DEFAULT = {
    "branch_id": "__default__",
    "theme": None,
    "config": {
        "restaurant": {"name": "Test Dhaba", "num_tables": 5},
        "items": [],
        "theme": {"primary_color": "#gold"},
    }
}

MOCK_STAFF_LIST = [
    {"id": 1, "username": "waiter1", "name": "Ramesh", "role": "waiter",
     "is_active": True,  "branch_id": "__default__"},
    {"id": 2, "username": "chef1",   "name": "Suresh", "role": "kitchen",
     "is_active": False, "branch_id": "__default__"},
]

MOCK_USER_OWNER = {
    "sub": "test_resto", "client_id": "test_resto",
    "role": "owner", "branch_id": None, "owner_id": 1,
}


class TestOwnerJson:
    """GET + PUT /api/owner/{client_id}/json"""

    def test_get_json_returns_config(self, owner_client):
        """Owner apna restaurant config padh sake"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_restaurant_branches", return_value=[MOCK_BRANCH_DEFAULT]):
            r = owner_client.get("/api/owner/test_resto/json")
        assert r.status_code == 200
        data = r.json()
        assert data["restaurant"]["name"] == "Test Dhaba"

    def test_get_json_branch_not_found_404(self, owner_client):
        """Wrong branch_id pe 404"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_restaurant_branches", return_value=[MOCK_BRANCH_DEFAULT]):
            r = owner_client.get("/api/owner/test_resto/json?branch_id=ghost_branch")
        assert r.status_code == 404

    def test_get_json_no_auth_rejected(self, client):
        """Bina auth ke config nahi milna chahiye"""
        r = client.get("/api/owner/test_resto/json")
        assert r.status_code in (302, 401, 403)

    def test_save_json_calls_save_restaurant(self, owner_client):
        """PUT pe save_restaurant_json DB function call hona chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_restaurant_branches", return_value=[MOCK_BRANCH_DEFAULT]), \
             patch("routers.owner.save_restaurant_json") as mock_save, \
             patch("routers.owner.seed_tables"):
            r = owner_client.put("/api/owner/test_resto/json", json={
                "data": {"restaurant": {"name": "New Name", "num_tables": 6}, "items": []}
            })
        assert r.status_code == 200
        mock_save.assert_called_once()

    def test_save_json_theme_preserved(self, owner_client):
        """Owner theme nahi badal sakta — existing theme preserve honi chahiye"""
        branch_with_theme = {
            **MOCK_BRANCH_DEFAULT,
            "theme": {"primary_color": "#gold", "font": "Playfair"},
        }
        saved_data = {}

        def capture_save(client_id, data, branch_id=None):
            saved_data.update(data)

        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_restaurant_branches", return_value=[branch_with_theme]), \
             patch("routers.owner.save_restaurant_json", side_effect=capture_save), \
             patch("routers.owner.seed_tables"):
            owner_client.put("/api/owner/test_resto/json", json={
                "data": {
                    "restaurant": {"name": "Hack Attempt", "num_tables": 5},
                    "theme": {"primary_color": "#hacked"},  # ← override try
                    "items": [],
                }
            })
        # Theme original wali rehni chahiye
        assert saved_data.get("theme") == {"primary_color": "#gold", "font": "Playfair"}

    def test_save_json_seeds_tables_if_num_tables_changes(self, owner_client):
        """num_tables change hone pe seed_tables call hona chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_restaurant_branches", return_value=[MOCK_BRANCH_DEFAULT]), \
             patch("routers.owner.save_restaurant_json"), \
             patch("routers.owner.seed_tables") as mock_seed:
            owner_client.put("/api/owner/test_resto/json", json={
                "data": {"restaurant": {"name": "Test", "num_tables": 10}, "items": []}
            })
        mock_seed.assert_called_once_with("test_resto", 10, "__default__")

    def test_save_json_no_auth_rejected(self, client):
        """Bina auth ke save nahi hona chahiye"""
        r = client.put("/api/owner/test_resto/json", json={"data": {}})
        assert r.status_code in (302, 401, 403)


class TestStaffGet:
    """GET /api/staff/{client_id}"""

    def test_returns_staff_list(self, owner_client):
        """Owner ko staff list milni chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_staff_list", return_value=MOCK_STAFF_LIST):
            r = owner_client.get("/api/staff/test_resto")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert data[0]["username"] == "waiter1"

    def test_get_staff_calls_db_with_client_id(self, owner_client):
        """get_staff_list sahi client_id se call hona chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_staff_list", return_value=[]) as mock_list:
            owner_client.get("/api/staff/test_resto")
        mock_list.assert_called_once_with("test_resto")

    def test_no_auth_rejected(self, client):
        r = client.get("/api/staff/test_resto")
        assert r.status_code in (302, 401, 403)


class TestStaffCreate:
    """POST /api/staff/{client_id}"""

    def test_create_staff_success(self, owner_client):
        """Naya staff create hona chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.create_staff", return_value=True):
            r = owner_client.post("/api/staff/test_resto", json={
                "username": "newwaiter",
                "password": "pass123",
                "name":     "Mahesh",
                "role":     "waiter",
            })
        assert r.status_code == 200
        assert "message" in r.json()

    def test_create_staff_calls_db(self, owner_client):
        """create_staff DB function sahi args se call hona chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.create_staff", return_value=True) as mock_create:
            owner_client.post("/api/staff/test_resto", json={
                "username": "chef2", "password": "pass",
                "name": "Dinesh", "role": "kitchen",
            })
        mock_create.assert_called_once()
        args = mock_create.call_args[0]
        assert args[0] == "test_resto"
        assert args[1] == "chef2"
        assert args[4] == "kitchen"

    def test_duplicate_username_409(self, owner_client):
        """Already exist karta username — 409 aana chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.create_staff", return_value=False):
            r = owner_client.post("/api/staff/test_resto", json={
                "username": "waiter1",  # duplicate
                "password": "pass", "name": "Copy", "role": "waiter",
            })
        assert r.status_code == 409

    def test_invalid_role_400(self, owner_client):
        """Invalid role pe 400 aana chahiye"""
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER):
            r = owner_client.post("/api/staff/test_resto", json={
                "username": "hacker", "password": "pass",
                "name": "Hacker", "role": "admin",  # ← invalid
            })
        assert r.status_code == 400

    def test_valid_roles_accepted(self, owner_client):
        """kitchen, waiter, counter, blogger — sab valid hain"""
        valid_roles = ["kitchen", "waiter", "counter", "blogger"]
        for role in valid_roles:
            with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
                 patch("routers.owner.create_staff", return_value=True):
                r = owner_client.post("/api/staff/test_resto", json={
                    "username": f"user_{role}", "password": "pass",
                    "name": role.title(), "role": role,
                })
            assert r.status_code == 200, f"{role} role reject hua unexpectedly"


class TestStaffPassword:
    """PATCH /api/staff/{client_id}/{staff_id}/password"""

    MOCK_STAFF_ROW = {"id": 1}

    def test_update_password_success(self, owner_client):
        """Password update hona chahiye"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = self.MOCK_STAFF_ROW
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn), \
             patch("routers.owner.update_staff_password") as mock_upd:
            r = owner_client.patch("/api/staff/test_resto/1/password",
                                   json={"new_password": "newsecure123"})
        assert r.status_code == 200
        mock_upd.assert_called_once_with(1, "newsecure123")

    def test_staff_not_found_404(self, owner_client):
        """Staff na mile toh 404"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn):
            r = owner_client.patch("/api/staff/test_resto/9999/password",
                                   json={"new_password": "x"})
        assert r.status_code == 404

    def test_empty_password_400(self, owner_client):
        """Empty password pe 400"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = self.MOCK_STAFF_ROW
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn):
            r = owner_client.patch("/api/staff/test_resto/1/password",
                                   json={"new_password": ""})
        assert r.status_code == 400


class TestStaffToggle:
    """PATCH /api/staff/{client_id}/{staff_id}/toggle"""

    def test_toggle_active_to_inactive(self, owner_client):
        """Active staff ko deactivate karo"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"is_active": True}
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn), \
             patch("routers.owner.toggle_staff_active") as mock_toggle:
            r = owner_client.patch("/api/staff/test_resto/1/toggle")
        assert r.status_code == 200
        assert r.json()["is_active"] is False       # True → False
        mock_toggle.assert_called_once_with(1, False)

    def test_toggle_inactive_to_active(self, owner_client):
        """Inactive staff ko activate karo"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"is_active": False}
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn), \
             patch("routers.owner.toggle_staff_active") as mock_toggle:
            r = owner_client.patch("/api/staff/test_resto/2/toggle")
        assert r.status_code == 200
        assert r.json()["is_active"] is True        # False → True
        mock_toggle.assert_called_once_with(2, True)

    def test_staff_not_found_404(self, owner_client):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn):
            r = owner_client.patch("/api/staff/test_resto/9999/toggle")
        assert r.status_code == 404


class TestStaffDelete:
    """DELETE /api/staff/{client_id}/{staff_id}"""

    def test_delete_success(self, owner_client):
        """Staff delete hona chahiye"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = {"id": 1}
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn), \
             patch("routers.owner.delete_staff") as mock_del:
            r = owner_client.delete("/api/staff/test_resto/1")
        assert r.status_code == 200
        mock_del.assert_called_once_with(1)

    def test_delete_nonexistent_staff_404(self, owner_client):
        """Na milne wale staff ko delete karna — 404"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn):
            r = owner_client.delete("/api/staff/test_resto/9999")
        assert r.status_code == 404

    def test_delete_wrong_restaurant_staff_404(self, owner_client):
        """Dusre restaurant ke staff ko delete karna — 404"""
        mock_conn = MagicMock()
        # client_id match nahi hoga DB query mein — None return hoga
        mock_conn.execute.return_value.fetchone.return_value = None
        with patch("routers.owner.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.owner.get_db", return_value=mock_conn):
            r = owner_client.delete("/api/staff/other_resto/1")
        assert r.status_code == 404
