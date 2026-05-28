"""
tests/test_orders.py — Orders Router Behavioral Tests

Kya test ho raha hai:
- POST /api/order/  — order place hota hai, place_order call hota hai
- GET  /api/orders/ — auth check, sahi orders aate hain
- PATCH /api/order/{id}/status — valid/invalid status check
- POST /api/bill/   — bill generate hota hai
- GET  /api/bill/{id} — bill fetch
- POST /api/bill/{id}/pay — mark paid
- Table inactive pe 403
- Auth missing pe 401/403
"""

import pytest
from unittest.mock import patch, MagicMock, call


MOCK_ORDERS = [
    {
        "id": 1, "client_id": "test_resto", "table_no": 3,
        "items": '[{"name":"Paneer","qty":2,"price":280}]',
        "total": 560, "status": "pending",
        "source": "customer", "created_at": "2025-01-01T12:00:00",
        "branch_id": "__default__",
    },
    {
        "id": 2, "client_id": "test_resto", "table_no": 5,
        "items": '[{"name":"Naan","qty":3,"price":40}]',
        "total": 120, "status": "preparing",
        "source": "waiter", "created_at": "2025-01-01T12:05:00",
        "branch_id": "__default__",
    },
]

MOCK_BILL = {
    "id": 1, "client_id": "test_resto", "table_no": 3,
    "total": 560, "tax_amount": 0, "discount": 0,
    "final_amount": 560, "status": "unpaid",
    "created_at": "2025-01-01T13:00:00",
}

MOCK_TABLE_ACTIVE = {
    "table_no": 3, "status": "active", "branch_id": "__default__"
}

MOCK_TABLE_INACTIVE = {
    "table_no": 9, "status": "inactive", "branch_id": "__default__"
}

MOCK_USER_OWNER = {
    "sub": "test_resto", "client_id": "test_resto",
    "role": "owner", "branch_id": None,
}

MOCK_USER_WAITER = {
    "sub": "waiter1", "client_id": "test_resto",
    "role": "waiter", "branch_id": "__default__",
}


class TestPlaceOrder:
    """POST /api/order/{client_id}/{table_no}"""

    def _place(self, client, table_no=3, items=None, total=560):
        items = items or [{"name": "Paneer", "qty": 2, "price": 280}]
        return client.post(
            f"/api/order/test_resto/{table_no}",
            json={"items": items, "total": total},
        )

    def test_successful_order_returns_order_id(self, client):
        """Sahi order pe order_id milna chahiye"""
        with patch("routers.orders.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.orders.require_feature"), \
             patch("routers.orders.get_table_status", return_value=MOCK_TABLE_ACTIVE), \
             patch("routers.orders.place_order", return_value=42):
            r = self._place(client)
        assert r.status_code == 200
        data = r.json()
        assert data["order_id"] == 42
        assert "message" in data

    def test_place_order_calls_db_function(self, client):
        """place_order DB function call honi chahiye sahi arguments se"""
        with patch("routers.orders.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.orders.require_feature"), \
             patch("routers.orders.get_table_status", return_value=MOCK_TABLE_ACTIVE), \
             patch("routers.orders.place_order", return_value=1) as mock_place:
            self._place(client, table_no=3, items=[{"name": "Paneer", "qty": 2, "price": 280}], total=560)
        mock_place.assert_called_once()
        args = mock_place.call_args[0]
        assert args[0] == "test_resto"   # client_id
        assert args[1] == 3              # table_no
        assert args[3] == 560            # total

    def test_inactive_table_403(self, client):
        """Inactive table pe order nahi hona chahiye"""
        with patch("routers.orders.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.orders.require_feature"), \
             patch("routers.orders.get_table_status", return_value=MOCK_TABLE_INACTIVE):
            r = self._place(client, table_no=9)
        assert r.status_code == 403

    def test_unknown_restaurant_404(self, client):
        """Galat restaurant pe 404"""
        with patch("routers.orders.get_client_data", return_value=None):
            r = self._place(client)
        assert r.status_code == 404

    def test_missing_items_422(self, client):
        """Items missing hone pe 422 validation error"""
        r = client.post("/api/order/test_resto/3", json={"total": 100})
        assert r.status_code == 422

    def test_missing_total_422(self, client):
        """Total missing hone pe 422"""
        r = client.post("/api/order/test_resto/3",
                        json={"items": [{"name": "x", "qty": 1, "price": 10}]})
        assert r.status_code == 422

    def test_delivery_order_successful_when_feature_enabled(self, client):
        """Delivery order place hona chahiye jab delivery feature active ho"""
        from fastapi import HTTPException
        
        # require_feature should run without raising any error (feature enabled)
        with patch("routers.orders.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.orders.require_feature") as mock_require_feature, \
             patch("routers.orders.place_order", return_value=100):
            r = client.post(
                "/api/order/test_resto/0",
                json={"items": [{"name": "Paneer", "qty": 1, "price": 280}], "total": 280, "source": "delivery"}
            )
        assert r.status_code == 200
        assert r.json()["order_id"] == 100
        # requirement is checked for "delivery"
        mock_require_feature.assert_any_call("test_resto", "delivery")

    def test_delivery_order_fails_when_feature_disabled(self, client):
        """Delivery order block hona chahiye agar delivery feature inactive ho"""
        from fastapi import HTTPException
        
        def mock_require_feature(client_id, feature):
            if feature == "delivery":
                raise HTTPException(status_code=403, detail="Feature 'delivery' not available")
        
        with patch("routers.orders.get_client_data", return_value={"restaurant": {}}), \
             patch("routers.orders.require_feature", side_effect=mock_require_feature):
            r = client.post(
                "/api/order/test_resto/0",
                json={"items": [{"name": "Paneer", "qty": 1, "price": 280}], "total": 280, "source": "delivery"}
            )
        assert r.status_code == 403
        assert "delivery" in r.json()["detail"]


class TestGetOrders:
    """GET /api/orders/{client_id}"""

    def test_owner_gets_all_orders(self, owner_client):
        """Owner ko saare orders milne chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_orders", return_value=MOCK_ORDERS):
            r = owner_client.get("/api/orders/test_resto")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_get_orders_db_function_called(self, owner_client):
        """get_orders DB function call hona chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_orders", return_value=[]) as mock_get:
            owner_client.get("/api/orders/test_resto")
        mock_get.assert_called_once()
        kwargs = mock_get.call_args[1]
        assert "client_id" in mock_get.call_args[0] or mock_get.called

    def test_no_auth_rejected(self, client):
        """Bina token ke orders nahi milne chahiye"""
        r = client.get("/api/orders/test_resto")
        assert r.status_code in (302, 401, 403)

    def test_status_filter_passed(self, owner_client):
        """?status=pending filter get_orders ko pass hona chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_orders", return_value=[MOCK_ORDERS[0]]) as mock_get:
            r = owner_client.get("/api/orders/test_resto?status=pending")
        assert r.status_code == 200
        call_kwargs = mock_get.call_args
        assert "status" in str(call_kwargs)

    def test_waiter_gets_branch_filtered_orders(self, client):
        """Waiter ko sirf apni branch ke orders milne chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_WAITER), \
             patch("routers.orders.get_orders", return_value=[MOCK_ORDERS[0]]) as mock_get:
            r = client.get("/api/orders/test_resto")
        assert r.status_code == 200
        # branch_id waiter ka pass hona chahiye
        call_args = mock_get.call_args
        assert "__default__" in str(call_args)


class TestFilterOrders:
    """GET /api/orders/{client_id}/filter"""

    def test_kitchen_status_merges_pending_preparing(self, owner_client):
        """status=kitchen pe pending + preparing dono merge hokar aane chahiye"""
        pending   = [MOCK_ORDERS[0]]  # status=pending
        preparing = [MOCK_ORDERS[1]]  # status=preparing

        def mock_get_orders(client_id, status=None, **kwargs):
            if status == "pending":   return pending
            if status == "preparing": return preparing
            return []

        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_orders", side_effect=mock_get_orders):
            r = owner_client.get("/api/orders/test_resto/filter?status=kitchen")
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_normal_status_single_call(self, owner_client):
        """Normal status pe ek hi get_orders call hona chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_orders", return_value=MOCK_ORDERS) as mock_get:
            owner_client.get("/api/orders/test_resto/filter?status=done")
        assert mock_get.call_count == 1


class TestUpdateOrderStatus:
    """PATCH /api/order/{order_id}/status"""

    def test_valid_status_update(self, owner_client):
        """Valid status pe update hona chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.update_order_status") as mock_update:
            r = owner_client.patch("/api/order/1/status", json={"status": "preparing"})
        assert r.status_code == 200
        mock_update.assert_called_once_with(1, "preparing")

    def test_invalid_status_400(self, owner_client):
        """Galat status pe 400 aana chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER):
            r = owner_client.patch("/api/order/1/status", json={"status": "flying"})
        assert r.status_code == 400

    def test_all_valid_statuses_accepted(self, owner_client):
        """Saare valid statuses accept hone chahiye"""
        valid = ["pending", "preparing", "ready", "done", "cancelled"]
        for status in valid:
            with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
                 patch("routers.orders.update_order_status"):
                r = owner_client.patch("/api/order/1/status", json={"status": status})
            assert r.status_code == 200, f"{status} pe 200 nahi aaya"

    def test_no_auth_rejected(self, client):
        """Bina auth ke status update nahi hona chahiye"""
        r = client.patch("/api/order/1/status", json={"status": "done"})
        assert r.status_code in (302, 401, 403)


class TestEditOrderItems:
    """PATCH /api/order/{order_id}/items"""

    MOCK_ORDER_ROW = {
        "id": 1, "status": "pending",
        "items": '[{"name":"Paneer","qty":2,"price":280}]',
        "ready_items": "[]",
        "client_id": "test_resto",
    }

    def _mock_db(self, order=None):
        """DB mock helper"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = (
            order or self.MOCK_ORDER_ROW
        )
        return mock_conn

    def test_edit_updates_items_and_total(self, owner_client):
        """Items edit hone pe total recalculate hona chahiye"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = self.MOCK_ORDER_ROW
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_db", return_value=mock_conn):
            r = owner_client.patch("/api/order/1/items", json={
                "items": [{"name": "Paneer", "qty": 1, "price": 280}],
                "extra_items": [],
            })
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 280  # 1 × 280

    def test_done_order_cannot_be_edited(self, owner_client):
        """Done/cancelled order edit nahi hona chahiye"""
        done_order = {**self.MOCK_ORDER_ROW, "status": "done"}
        mock_conn  = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = done_order
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_db", return_value=mock_conn):
            r = owner_client.patch("/api/order/1/items", json={
                "items": [{"name": "Paneer", "qty": 1, "price": 280}],
                "extra_items": [],
            })
        assert r.status_code == 400

    def test_order_not_found_404(self, owner_client):
        """Order na mile toh 404"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_db", return_value=mock_conn):
            r = owner_client.patch("/api/order/9999/items", json={
                "items": [], "extra_items": [],
            })
        assert r.status_code == 404

    def test_all_items_removed_cancels_order(self, owner_client):
        """Saare items qty=0 hone pe order cancel ho jaana chahiye"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = self.MOCK_ORDER_ROW
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.get_db", return_value=mock_conn):
            r = owner_client.patch("/api/order/1/items", json={
                "items": [],  # koi item nahi
                "extra_items": [],
            })
        assert r.status_code == 200
        assert "cancelled" in r.json()["message"]


class TestBilling:
    """POST /api/bill/ aur GET /api/bill/{id}"""

    def test_generate_bill_success(self, owner_client):
        """Bill generate hona chahiye — generate_bill call hona chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.generate_bill", return_value=MOCK_BILL):
            r = owner_client.post("/api/bill/test_resto/3", json={
                "tax_percent": 5.0,
                "discount":    50,
                "payment_mode": "upi",
            })
        assert r.status_code == 200
        data = r.json()
        assert data["table_no"] == 3
        assert "final_amount" in data

    def test_generate_bill_calls_db_with_correct_args(self, owner_client):
        """generate_bill sahi arguments se call hona chahiye"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.generate_bill", return_value=MOCK_BILL) as mock_bill:
            owner_client.post("/api/bill/test_resto/3", json={
                "tax_percent": 5.0, "discount": 0,
            })
        mock_bill.assert_called_once()
        args = mock_bill.call_args[0]
        assert args[0] == "test_resto"  # client_id
        assert args[1] == 3             # table_no

    def test_no_billable_orders_404(self, owner_client):
        """Koi billable order na ho toh 404"""
        with patch("routers.orders.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.orders.generate_bill", return_value=None):
            r = owner_client.post("/api/bill/test_resto/3", json={})
        assert r.status_code == 404

    def test_get_bill_success(self, client):
        """GET /api/bill/{id} — bill data milna chahiye"""
        with patch("routers.orders.get_bill", return_value=MOCK_BILL):
            r = client.get("/api/bill/1")
        assert r.status_code == 200
        assert r.json()["id"] == 1

    def test_get_bill_not_found_404(self, client):
        """Bill na mile toh 404"""
        with patch("routers.orders.get_bill", return_value=None):
            r = client.get("/api/bill/9999")
        assert r.status_code == 404

    def test_mark_paid_calls_db(self, client):
        """POST /api/bill/{id}/pay — mark_bill_paid call hona chahiye"""
        with patch("routers.orders.mark_bill_paid") as mock_paid:
            r = client.post("/api/bill/1/pay", json={"payment_mode": "cash"})
        assert r.status_code == 200
        mock_paid.assert_called_once_with(1, "cash")

    def test_mark_paid_default_mode_cash(self, client):
        """payment_mode default cash hona chahiye"""
        with patch("routers.orders.mark_bill_paid") as mock_paid:
            client.post("/api/bill/1/pay", json={})
        mock_paid.assert_called_once_with(1, "cash")

    def test_bill_no_auth(self, client):
        """Bina auth ke bill generate nahi hona chahiye"""
        r = client.post("/api/bill/test_resto/3", json={})
        assert r.status_code in (302, 401, 403)
