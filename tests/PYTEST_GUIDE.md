# ZenTable — Pytest Master Guide (Pytest Ki Complete Guide) 🧪

ZenTable ek fully-tested multi-tenant platform hai jismein **~166 automated unit & behavioral tests** likhe gaye hain. Ye tests fast, offline, aur completely secure hain kyunki ye main database (Neon PostgreSQL) ko touch nahi karte, balki use mock karte hain.

---

## 1. Setup & Environment Configurations

Tests run karne se pehle ensure karein ki virtual environment (`.venv`) activated hai aur required dependencies installed hain.

### Virtual Environment Setup & Dependencies
```bash
# Virtual environment ko activate karein (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Test libraries ko install karein (agar already nahi hain)
pip install pytest httpx
```

### Environment Variables
Pytest run karte waqt `SECRET_KEY` env variable pass karna mandatory hai, warna JWT/auth module key error throw karega:
- **Windows (PowerShell):** `$env:SECRET_KEY="test"; pytest tests/`
- **Linux/macOS:** `SECRET_KEY=test pytest tests/`

---

## 2. Hum Kya Test Karte Hain Aur Kaise? (What to Test & How)

ZenTable mein testing ko teen alag objectives ke liye split kiya gaya hai:

```
┌────────────────────────────────────────────────────────┐
│                   ZenTable Test Suite                  │
└───────────────────────────┬────────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────┐
 │ Level 1: Smoke Tests (test_smoke.py)                 │
 │ - Kya saare routes aur pages bina 500 error ke load  │
 │   ho rahe hain?                                      │
 └──────────────────────────┬───────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────┐
 │ Level 2: Behavioral Tests (test_billing.py, etc.)    │
 │ - Kya features exact roles ke according locked hain? │
 │ - Kya incorrect passwords reject ho rahe hain?        │
 └──────────────────────────┬───────────────────────────┘
                            ▼
 ┌──────────────────────────────────────────────────────┐
 │ Level 3: Database Mocking & Isolation (conftest.py)  │
 │ - PostgreSQL connections ko mock database cursor se  │
 │   replace karna taaki real DB change na ho.          │
 └──────────────────────────────────────────────────────┘
```

### A. Smoke Tests (Kya 500 Error Nahi Aata?)
`tests/test_smoke.py` mein har ek endpoint ko ping kiya jaata hai taaki ensure ho sake ki koi import crash ya missing parameter server-level syntax error (`500 Internal Server Error`) trigger nahi kar raha.

### B. Behavioral Tests (Kya Functionality Sahi Hai?)
Apne business logic aur route behaviors ko check karne ke liye:
- **Role-based Authentication:** Waiter, Counter, Kitchen, Owner, aur Admin ki roles ki checking.
- **Feature Gating:** Basic plan ka owner Pro features (jaise owner analytics ya multi-branch) ko access nahi kar paana chahiye unless addon/upgrade purchased ho.

### C. Database Mocking & Isolation
`tests/conftest.py` saare database functions (jaise Neon PostgreSQL query connections) ko intercept karke mock cursors and mock return values inject karta hai.
> [!IMPORTANT]
> Iska matlab hai ki test suit chalate waqt aapka actual live databases bilkul touch nahi hota aur aap test records ko bina database dependency ke verify kar sakte hain.

---

## 3. Pytest Commands Cheatsheet (Pytest Kaise Run Karein?)

| Run Objective | Windows (PowerShell) Command | Linux / macOS Command |
| :--- | :--- | :--- |
| **Saare 160+ Tests Run Karein** | `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/ -v` | `SECRET_KEY=test pytest tests/ -v` |
| **Sirf Ek Specific File** | `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/test_billing.py -v` | `SECRET_KEY=test pytest tests/test_billing.py -v` |
| **Sirf Ek Specific Class** | `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/test_orders.py::TestPlaceOrder -v` | `SECRET_KEY=test pytest tests/test_orders.py::TestPlaceOrder -v` |
| **Sirf Ek Specific Test Function**| `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/test_owner.py::TestStaffToggle::test_toggle_active_to_inactive -v` | `SECRET_KEY=test pytest tests/test_owner.py::TestStaffToggle::test_toggle_active_to_inactive -v` |
| **Search/Filter By Name (`-k`)** | `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/ -k "menu" -v` | `SECRET_KEY=test pytest tests/ -k "menu" -v` |
| **Peechla Failed Test Dobara Run (`-lf`)** | `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/ -lf -v` | `SECRET_KEY=test pytest tests/ -lf -v` |
| **Pehle Failure Par Stop Karein (`-x`)** | `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/ -x -v` | `SECRET_KEY=test pytest tests/ -x -v` |
| **Quiet/Condensed Output (`-q`)** | `$env:SECRET_KEY="test"; .venv\Scripts\pytest tests/ -q` | `SECRET_KEY=test pytest tests/ -q` |

---

## 4. Test Results aur Unke Visual Meanings (Pass, Fail, Error)

Pytest run karne par aapko terminal par teen tarah ke status milenge. Unka breakdown aur practical demonstration neeche diya gaya hai:

```
📊 PYTEST RESULTS AT A GLANCE:
───────────────────────────────────────────────────────────
   . (Passed)  ──> Sab kuch sahi hai, assertion matches.
   F (Failed)  ──> Code chala par output galat aaya (Assertion failed).
   E (Error)   ──> Code crash ho gaya ya test logic mein exception aayi.
───────────────────────────────────────────────────────────
```

### 🔴 Scenario A: PASS (Status Code: Green `.`)
**Kab hota hai?**
Jab test code chala aur usne exactly wahi deliver kiya jo assert block ne demand kiya tha.

**Code Example:**
```python
def test_menu_endpoint(client):
    # Public menu check: returns 200 OK
    response = client.get("/test_resto/menu")
    assert response.status_code == 200  # <--- PASS! (status 200 hi aaya)
```
**Terminal Output:**
```text
tests/test_menu.py::test_menu_endpoint PASSED    [ 100%]
```

---

### 🟡 Scenario B: FAIL (Status Code: Red `F`)
**Kab hota hai?**
Code successfully execute hua, koi python crashing/error nahi aayi, par jo value return hui wo assert block se match nahi hui.

**Code Example:**
```python
def test_locked_feature_access(client):
    # Basic tier par locked route pe request mari
    response = client.get("/api/owner/analytics")
    
    # Hum expect kar rahe the ki locking ki wajah se 403 Forbidden aayega
    # Par humne galti se assert status 200 likh diya
    assert response.status_code == 200  # <--- FAIL! (Actual output is 403)
```

**Terminal Output aur Assertion Error Tracing:**
```text
___________________________ test_locked_feature_access ___________________________

client = <httpx.Client object at 0x00000188A3>

    def test_locked_feature_access(client):
        response = client.get("/api/owner/analytics")
>       assert response.status_code == 200
E       assert 403 == 200
E        +  where 403 = <Response [403 Forbidden]>.status_code

tests/test_owner.py:42: AssertionError
=========================== 1 failed in 0.45s ===========================
```
> [!TIP]
> **Fix Kaise Karein?** Terminal Traceback ko read karein. Line `E assert 403 == 200` saaf bata rahi hai ki actual value `403` aayi, par hum `200` expect kar rahe the. Logic fix karein ya test assertion ko `assert response.status_code == 403` par change karein.

---

### ❌ Scenario C: ERROR (Status Code: Red `E`)
**Kab hota hai?**
Test ka setup/teardown code hi crash ho gaya ya route logic ke andar exception raise ho gayi (jaise division by zero, syntax errors, missing imports, ya `NoneType has no attribute`).

**Code Example:**
```python
def test_restaurant_stats(client):
    # Galti se import galat path par ho gaya ya variable defined nahi hai
    non_existent_helper.calculate() # <--- Pytest will raise NameError
    
    response = client.get("/api/admin/stats")
    assert response.status_code == 200
```

**Terminal Output aur Exception Tracing:**
```text
___________________________ test_restaurant_stats ___________________________

client = <httpx.Client object at 0x00000188B5>

    def test_restaurant_stats(client):
>       non_existent_helper.calculate()
E       NameError: name 'non_existent_helper' is not defined

tests/test_admin.py:10: NameError
=========================== 1 error in 0.12s ===========================
```
> [!WARNING]
> **Assertion Failure aur Error mein difference:**
> - **Failure (F)** ka matlab hai platform run ho raha hai, par logic galat hai.
> - **Error (E)** ka matlab hai platform or tests crash ho gaye hain.

---

## 5. Naya Test Kaise Likhein? (Step-by-Step Tutorial)

Maan lijiye aapne ek naya feature develop kiya: `/api/owner/discount-coupon` (Staff can create custom coupons). Isko test karne ke liye do levels ke tests likhe jayenge:

### Step 1: Smoke Test Likhein (`tests/test_smoke.py`)
Ensure karein ki endpoint unauthenticated states mein 500 error na throw kare.
```python
class TestDiscountCouponSmoke:
    def test_coupon_listing_no_auth(self, client):
        # Unauthenticated request direct check
        response = client.get("/api/owner/discount-coupon")
        # 401 Unauthorized expected hai, par 500 internal server error nahi hona chahiye
        assert response.status_code not in (500,)
```

### Step 2: Behavioral Test Likhein (`tests/test_owner.py`)
Yahan Mocking dynamic DB and role protection verify karein.
```python
from unittest.mock import patch

class TestDiscountCouponCreation:
    
    def test_successful_coupon_creation(self, owner_client):
        """Owner dashboard par valid coupon create hona chahiye"""
        mock_coupon_data = {"code": "FRESH10", "discount_pct": 10}
        
        # database calls aur session verification ko patch (mock) karein
        with patch("routers.owner.place_new_coupon", return_value=True), \
             patch("routers.owner.require_auth", return_value={"username": "chef_resto", "role": "owner"}):
             
            response = owner_client.post("/api/owner/discount-coupon", json=mock_coupon_data)
            
        # Check: Successful validation returns 200 OK
        assert response.status_code == 200
        assert response.json() == {"status": "success", "message": "Coupon created!"}

    def test_feature_locked_for_basic_plan(self, owner_client):
        """Basic Plan wale restaurant ke liye coupons lock hone chahiye (403 expected)"""
        from fastapi import HTTPException
        mock_coupon_data = {"code": "FRESH10", "discount_pct": 10}
        
        with patch("routers.owner.require_auth", return_value={"username": "chef_resto", "role": "owner"}), \
             patch("routers.owner.require_feature", side_effect=HTTPException(status_code=403, detail="Feature locked")):
             
            response = owner_client.post("/api/owner/discount-coupon", json=mock_coupon_data)
            
        assert response.status_code == 403
```

---

## 6. Common Failures aur Troubleshooting (Gotchas!)

1. **`ModuleNotFoundError: No module named 'routers'`**
   - **Reason:** Pytest ko root folder path nahi pata chala.
   - **Fix:** Apne root directory (`Demo/`) par jaakar command ko execute karein: `.venv\Scripts\pytest tests/`

2. **`KeyError: 'SECRET_KEY'`**
   - **Reason:** Secret key define nahi ki test environment variables mein.
   - **Fix:** Running command se pehle `$env:SECRET_KEY="test"` execute karein (ya terminal environment me configure karein).

3. **`AttributeError / Mock issues`**
   - **Reason:** Target path galat specify kiya mock module patch mein.
   - **Rule of Thumb:** Hamesha us target file path ko patch karein jahan function **import aur call** ho raha hai, na ki us file ko jahan wo define hai. 
   - *Example:* Agar `database.py` ka `get_db` function `routers/menu.py` mein use ho raha hai, to mock patch path `routers.menu.get_db` hoga, na ki `database.get_db`.
