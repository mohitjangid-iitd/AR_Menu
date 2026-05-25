# ZenTable — Tests

## Setup

```bash
pip install pytest httpx
```

---

## Run Karo

```bash
# Saare tests
SECRET_KEY=test pytest tests/ -v

# Sirf ek file
pytest tests/test_billing.py -v

# Sirf ek class
pytest tests/test_orders.py::TestPlaceOrder -v

# Sirf ek test
pytest tests/test_owner.py::TestStaffToggle::test_toggle_active_to_inactive -v

# Short output
pytest tests/ -q

# Failures sirf
pytest tests/ -v --tb=short
```

---

## Files aur Coverage

| File | Kya cover hota hai | Tests |
|------|--------------------|-------|
| `conftest.py` | App setup, DB mocks, fixtures | — |
| `test_smoke.py` | Har API — 500 nahi aana chahiye | ~20 |
| `test_billing.py` | Feature locking, plan checks, billing APIs | ~25 |
| `test_menu.py` | Menu fetch, GLB token, model_url | ~8 |
| `test_orders.py` | Order CRUD, bill, status updates | ~22 |
| `test_owner.py` | Staff CRUD, config save, theme lock | ~20 |
| `test_tables.py` | Table activate/close, waiter call | ~18 |
| `test_admin.py` | Admin APIs, site settings, restaurant mgmt | ~20 |

**Total: ~133 tests**

---

## Teen Levels of Testing

```
Level 1 — Smoke        "Kya 500 nahi aata?"       test_smoke.py
Level 2 — Behavioral   "Sahi kaam karta hai?"     baaki sab files
Level 3 — Integration  "Real DB ke saath?"        abhi nahi (future)
```

---

## Ye Tests Neon DB Touch NAHI Karte

Saara DB mock hai. Sirf ye chahiye:

```bash
SECRET_KEY=any-string pytest tests/ -v
```

---

## Naya Feature Add Kiya — Test Kaise Likhein

### 1. Smoke test add karo (`test_smoke.py`)

```python
class TestInventoryRoutes:
    def test_inventory_no_auth(self, client):
        r = client.get("/api/inventory/test_resto/items")
        assert r.status_code not in (500,)
```

### 2. Behavioral test file banao (`test_inventory.py`)

```python
class TestInventoryGet:
    def test_returns_items(self, owner_client):
        with patch("routers.inventory.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.inventory.get_inventory_items", return_value=[...]):
            r = owner_client.get("/api/inventory/test_resto/items")
        assert r.status_code == 200

    def test_feature_locked_on_basic(self, owner_client):
        """Basic plan pe 403 aana chahiye"""
        with patch("routers.inventory.require_auth", return_value=MOCK_USER_OWNER), \
             patch("routers.inventory.require_feature",
                   side_effect=HTTPException(403, "locked")):
            r = owner_client.get("/api/inventory/test_resto/items")
        assert r.status_code == 403
```

---

## Common Failures aur Fix

| Error | Reason | Fix |
|-------|--------|-----|
| `ModuleNotFoundError` | Root se nahi chala | `cd project && pytest tests/ -v` |
| `KeyError: SECRET_KEY` | Env var nahi | `SECRET_KEY=test pytest tests/ -v` |
| `assert 500 not in ...` | Route mein actual bug | `-v --tb=long` se dekho exact error |
| Mock patch path galat | `routers.menu.get_client_data` sahi path nahi | Jahan function use hota hai wahan patch karo, jahan define hota hai nahi |
