"""
tests/test_menu.py — Menu Router Behavioral Tests

Kya test ho raha hai:
- GET /api/menu/{client_id} — sahi data aata hai, GLB token banta hai
- GET /glb/{token} — valid token pe file milti hai, invalid pe 403
- Restaurant na mile toh 404
- GLB token expire ho toh 403
"""

import pytest
from unittest.mock import patch, MagicMock


MOCK_MENU_DATA = {
    "restaurant": {"name": "Test Dhaba", "num_tables": 5},
    "items": [
        {"id": 1, "name": "Paneer Butter Masala", "price": 280, "model": "paneer.glb"},
        {"id": 2, "name": "Dal Makhani",           "price": 220, "model": "none"},
        {"id": 3, "name": "Naan",                  "price": 40,  "model": None},
    ],
    "categories": ["Main Course", "Bread"],
}


class TestMenuGet:
    """GET /api/menu/{client_id} — menu data fetch"""

    def test_returns_menu_data(self, client):
        """Sahi client_id pe menu data aana chahiye"""
        with patch("routers.menu.get_client_data", return_value=MOCK_MENU_DATA), \
             patch("routers.menu.create_glb_token", return_value="fake-token-123"):
            r = client.get("/api/menu/test_resto")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert data["restaurant"]["name"] == "Test Dhaba"

    def test_items_count_correct(self, client):
        """Items ki count sahi honi chahiye"""
        with patch("routers.menu.get_client_data", return_value=MOCK_MENU_DATA), \
             patch("routers.menu.create_glb_token", return_value="fake-token"):
            r = client.get("/api/menu/test_resto")
        assert len(r.json()["items"]) == 3

    def test_glb_item_gets_model_url(self, client):
        """Agar item mein model hai toh model_url banna chahiye"""
        with patch("routers.menu.get_client_data", return_value=MOCK_MENU_DATA), \
             patch("routers.menu.create_glb_token", return_value="signed-token-abc"):
            r = client.get("/api/menu/test_resto")
        items = r.json()["items"]
        paneer = next(i for i in items if i["name"] == "Paneer Butter Masala")
        assert paneer["model_url"] == "/glb/signed-token-abc"

    def test_none_model_item_gets_null_url(self, client):
        """model=none ya null hone pe model_url None hona chahiye"""
        with patch("routers.menu.get_client_data", return_value=MOCK_MENU_DATA), \
             patch("routers.menu.create_glb_token", return_value="token"):
            r = client.get("/api/menu/test_resto")
        items = r.json()["items"]
        dal   = next(i for i in items if i["name"] == "Dal Makhani")
        naan  = next(i for i in items if i["name"] == "Naan")
        assert dal["model_url"]  is None
        assert naan["model_url"] is None

    def test_unknown_restaurant_404(self, client):
        """Galat client_id pe 404 aana chahiye"""
        with patch("routers.menu.get_client_data", return_value=None):
            r = client.get("/api/menu/ghost_resto_xyz")
        assert r.status_code == 404

    def test_create_glb_token_called_for_model_items(self, client):
        """GLB model wale items ke liye create_glb_token call hona chahiye"""
        with patch("routers.menu.get_client_data", return_value=MOCK_MENU_DATA) as _, \
             patch("routers.menu.create_glb_token", return_value="tok") as mock_token:
            client.get("/api/menu/test_resto")
        # Sirf 1 item mein valid model hai (paneer.glb) — 1 baar call hona chahiye
        assert mock_token.call_count == 1
        mock_token.assert_called_with("test_resto", "paneer.glb")

    def test_original_data_not_mutated(self, client):
        """Deep copy hoti hai — original data mein model_url nahi aana chahiye"""
        import copy
        original = copy.deepcopy(MOCK_MENU_DATA)
        with patch("routers.menu.get_client_data", return_value=MOCK_MENU_DATA), \
             patch("routers.menu.create_glb_token", return_value="tok"):
            client.get("/api/menu/test_resto")
        # Original data mein model_url nahi hona chahiye
        for item in MOCK_MENU_DATA["items"]:
            assert "model_url" not in item

    def test_branch_id_passed_to_get_client_data(self, client):
        """branch_id query param get_client_data ko pass hona chahiye"""
        with patch("routers.menu.get_client_data", return_value=MOCK_MENU_DATA) as mock_gcd, \
             patch("routers.menu.create_glb_token", return_value="tok"):
            client.get("/api/menu/test_resto?branch_id=branch_2")
        mock_gcd.assert_called_with("test_resto", branch_id="branch_2")


class TestGlbServe:
    """GET /glb/{token} — signed token se GLB file"""

    def test_invalid_token_403(self, client):
        """Invalid token pe 403 aana chahiye"""
        with patch("routers.menu.verify_glb_token", return_value=None):
            r = client.get("/glb/invalid-token-xyz")
        assert r.status_code == 403

    def test_valid_token_r2_redirect(self, client):
        """Valid token + R2 enabled — presigned URL pe redirect hona chahiye"""
        with patch("routers.menu.verify_glb_token", return_value=("test_resto", "test_resto/paneer.glb")), \
             patch("routers.menu.USE_R2", True), \
             patch("routers.menu.r2_presign", return_value="https://r2.example.com/paneer.glb?sig=abc"):
            r = client.get("/glb/valid-token", follow_redirects=False)
        assert r.status_code == 302
        assert "r2.example.com" in r.headers["location"]

    def test_valid_token_local_file_not_found(self, client):
        """Valid token + local + file missing — 404 aana chahiye"""
        with patch("routers.menu.verify_glb_token", return_value=("test_resto", "test_resto/missing.glb")), \
             patch("routers.menu.USE_R2", False), \
             patch("os.path.exists", return_value=False):
            r = client.get("/glb/valid-token")
        assert r.status_code == 404

    def test_expired_token_403(self, client):
        """Expire hua token — verify_glb_token None deta hai — 403 aana chahiye"""
        with patch("routers.menu.verify_glb_token", return_value=None):
            r = client.get("/glb/expired-token-abc")
        assert r.status_code == 403
