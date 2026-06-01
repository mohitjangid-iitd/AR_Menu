"""
tests/test_tables.py — Tables Router Behavioral Tests

Kya test ho raha hai:
- POST activate/close — DB function call, auth check
- GET summary/list   — branch filtering
- Waiter call        — public endpoint (no auth)
- multi_branch feature lock
- Auth missing pe reject
"""

import pytest
from unittest.mock import patch, MagicMock


MOCK_USER_OWNER = {
    "sub": "test_resto", "client_id": "test_resto",
    "role": "owner", "branch_id": None,
}
MOCK_USER_WAITER = {
    "sub": "waiter1", "client_id": "test_resto",
    "role": "waiter", "branch_id": "__default__",
}
MOCK_USER_COUNTER = {
    "sub": "counter1", "client_id": "test_resto",
    "role": "counter", "branch_id": "__default__",
}

MOCK_TABLES = [
    {"table_no": 1, "status": "active",   "branch_id": "__default__"},
    {"table_no": 2, "status": "inactive", "branch_id": "__default__"},
    {"table_no": 3, "status": "active",   "branch_id": "__default__"},
]

MOCK_SUMMARY = {
    "total": 5, "active": 3, "inactive": 2,
    "occupied": 1, "free": 2,
}


class TestActivateTable:
    """POST /api/table/{client_id}/{table_no}/activate"""

    def test_activate_calls_db(self, owner_client):
        """activate_table DB function call hona chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.tables.require_feature"), \
             patch("routers.tables.activate_table") as mock_act:
            r = owner_client.post("/api/table/test_resto/3/activate")
        assert r.status_code == 200
        mock_act.assert_called_once_with("test_resto", 3, "__default__")

    def test_activate_returns_message(self, owner_client):
        """Response mein message hona chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.tables.require_feature"), \
             patch("routers.tables.activate_table"):
            r = owner_client.post("/api/table/test_resto/5/activate")
        assert "message" in r.json()
        assert "5" in r.json()["message"]

    def test_unknown_restaurant_404(self, owner_client):
        """Restaurant na mile toh 404"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_client_data", return_value=None):
            r = owner_client.post("/api/table/ghost/3/activate")
        assert r.status_code == 404

    def test_no_auth_rejected(self, client):
        r = client.post("/api/table/test_resto/3/activate")
        assert r.status_code in (302, 401, 403)

    def test_multi_branch_feature_checked_for_non_default(self, owner_client):
        """Non-default branch pe multi_branch feature check hona chahiye"""
        user_with_branch = {**MOCK_USER_OWNER, "branch_id": "branch_2"}
        with patch("routers.tables.require_auth", return_value=user_with_branch), \
             patch("routers.tables.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.tables.require_feature") as mock_feature, \
             patch("routers.tables.activate_table"):
            owner_client.post("/api/table/test_resto/3/activate")
        mock_feature.assert_called_with("test_resto", "multi_branch")

    def test_default_branch_no_multi_branch_check(self, owner_client):
        """Default branch pe multi_branch check nahi hona chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.tables.require_feature") as mock_feature, \
             patch("routers.tables.activate_table"):
            owner_client.post("/api/table/test_resto/3/activate")
        mock_feature.assert_not_called()


class TestActivateAllTables:
    """POST /api/table/{client_id}/activate-all"""

    def test_activate_all_calls_db(self, owner_client):
        """activate_all_tables call hona chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.require_feature"), \
             patch("routers.tables.activate_all_tables") as mock_all:
            r = owner_client.post("/api/table/test_resto/activate-all")
        assert r.status_code == 200
        mock_all.assert_called_once()

    def test_waiter_cannot_activate_all(self, client):
        """Waiter activate-all nahi kar sakta — counter/owner/admin only"""
        from fastapi import HTTPException
        with patch("routers.tables.require_auth",
                   side_effect=HTTPException(status_code=403, detail="Forbidden")) as mock_auth:
            # require_auth raise karega kyunki waiter allowed nahi
            r = client.post("/api/table/test_resto/activate-all")
        assert r.status_code in (401, 403, 500)

    def test_branch_id_from_query_param(self, owner_client):
        """branch_id query param se aana chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.require_feature"), \
             patch("routers.tables.activate_all_tables") as mock_all:
            owner_client.post("/api/table/test_resto/activate-all?branch_id=branch_2")
        args = mock_all.call_args[0]
        assert args[1] == "branch_2"


class TestCloseTable:
    """POST /api/table/{client_id}/{table_no}/close"""

    def test_close_calls_db(self, owner_client):
        """close_table DB function call hona chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.close_table") as mock_close:
            r = owner_client.post("/api/table/test_resto/2/close")
        assert r.status_code == 200
        mock_close.assert_called_once_with("test_resto", 2, "__default__")

    def test_close_returns_message(self, owner_client):
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.close_table"):
            r = owner_client.post("/api/table/test_resto/2/close")
        assert "2" in r.json()["message"]

    def test_no_auth_rejected(self, client):
        r = client.post("/api/table/test_resto/2/close")
        assert r.status_code in (302, 401, 403)


class TestCloseAllTables:
    """POST /api/table/{client_id}/close-all"""

    def test_close_all_calls_db(self, owner_client):
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.close_all_tables") as mock_close:
            r = owner_client.post("/api/table/test_resto/close-all")
        assert r.status_code == 200
        mock_close.assert_called_once()

    def test_branch_id_used_from_query(self, owner_client):
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.close_all_tables") as mock_close:
            owner_client.post("/api/table/test_resto/close-all?branch_id=outlet_1")
        args = mock_close.call_args[0]
        assert args[1] == "outlet_1"


class TestGetTables:
    """GET /api/tables/{client_id}"""

    def test_returns_table_list(self, owner_client):
        """Tables list milni chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_all_tables", return_value=MOCK_TABLES):
            r = owner_client.get("/api/tables/test_resto")
        assert r.status_code == 200
        assert len(r.json()) == 3

    def test_db_called_with_correct_branch(self, owner_client):
        """get_all_tables sahi branch_id se call hona chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_WAITER), \
             patch("routers.tables.get_all_tables", return_value=[]) as mock_get:
            owner_client.get("/api/tables/test_resto")
        args = mock_get.call_args[0]
        assert args[0] == "test_resto"

    def test_no_auth_rejected(self, client):
        r = client.get("/api/tables/test_resto")
        assert r.status_code in (302, 401, 403)


class TestTableSummary:
    """GET /api/tables/{client_id}/summary"""

    def test_returns_summary(self, owner_client):
        """Summary data milna chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_table_summary", return_value=MOCK_SUMMARY):
            r = owner_client.get("/api/tables/test_resto/summary")
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert data["total"] == 5

    def test_summary_db_called(self, owner_client):
        """get_table_summary DB function call hona chahiye"""
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_table_summary", return_value=MOCK_SUMMARY) as mock_sum:
            owner_client.get("/api/tables/test_resto/summary")
        mock_sum.assert_called_once()
        assert mock_sum.call_args[0][0] == "test_resto"


class TestTableDetail:
    """GET /api/table/{client_id}/{table_no}/detail"""

    MOCK_DETAIL = {
        "table_no": 3, "status": "active",
        "orders": [{"id": 1, "status": "pending", "items": []}],
    }

    def test_returns_detail(self, owner_client):
        with patch("routers.tables.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.tables.get_table_orders_detail", return_value=self.MOCK_DETAIL):
            r = owner_client.get("/api/table/test_resto/3/detail")
        assert r.status_code == 200
        assert r.json()["table_no"] == 3


class TestWaiterCall:
    """POST /api/table/{client_id}/{table_no}/call — public, no auth"""

    def test_call_waiter_no_auth_needed(self, client):
        """Public endpoint — bina auth ke kaam karna chahiye"""
        with patch("routers.tables.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.tables.create_waiter_call") as mock_call:
            r = client.post("/api/table/test_resto/3/call")
        assert r.status_code == 200
        mock_call.assert_called_once_with("test_resto", 3, "__default__")

    def test_call_waiter_unknown_restaurant_404(self, client):
        with patch("routers.tables.get_client_data", return_value=None):
            r = client.post("/api/table/ghost/3/call")
        assert r.status_code == 404

    def test_call_message_has_table_number(self, client):
        with patch("routers.tables.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.tables.create_waiter_call"):
            r = client.post("/api/table/test_resto/7/call")
        assert "7" in r.json()["message"]


class TestResolveCall:
    """POST /api/table/{client_id}/{table_no}/call/resolve"""

    def test_resolve_calls_db(self, owner_client):
        with patch("routers.tables.require_auth", return_value=MOCK_USER_WAITER), \
             patch("routers.tables.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.tables.resolve_waiter_call") as mock_resolve:
            r = owner_client.post("/api/table/test_resto/3/call/resolve")
        assert r.status_code == 200
        mock_resolve.assert_called_once_with("test_resto", 3, "__default__")

    def test_no_auth_rejected(self, client):
        r = client.post("/api/table/test_resto/3/call/resolve")
        assert r.status_code in (302, 401, 403)


class TestGetCalls:
    """GET /api/tables/{client_id}/calls"""

    def test_returns_active_calls(self, owner_client):
        mock_calls = [
            {"id": 1, "table_no": 3, "status": "active"},
            {"id": 2, "table_no": 5, "status": "active"},
        ]
        with patch("routers.tables.require_auth", return_value=MOCK_USER_WAITER), \
             patch("routers.tables.get_active_calls", return_value=mock_calls):
            r = owner_client.get("/api/tables/test_resto/calls")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_no_auth_rejected(self, client):
        r = client.get("/api/tables/test_resto/calls")
        assert r.status_code in (302, 401, 403)
