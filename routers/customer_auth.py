"""
routers/customer_auth.py — Customer Google OAuth flow
Delivery orders ke liye customer login/logout

Endpoints:
  GET   /auth/google
  GET   /auth/google/callback
  GET   /auth/customer/logout
  GET   /api/customer/me
  POST  /api/customer/profile
  GET   /api/customer/orders
"""

import os
import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from db import get_or_create_customer, get_customer_by_id
from auth import create_token
from datetime import timedelta

router = APIRouter()

GOOGLE_CLIENT_ID     = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_AUTH_URL      = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL     = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

def get_redirect_uri(request: Request) -> str:
    """Prod vs local dono handle karo"""
    base = str(request.base_url).rstrip("/")
    return f"{base}/auth/google/callback"


# ── Step 1: Google pe redirect karo ──
@router.get("/auth/google")
async def google_login(request: Request, next: str = "/"):
    """
    Customer Google login initiate karo.
    ?next= param se post-login redirect URL pass karo.
    Example: /auth/google?next=/zomato/menu
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    redirect_uri = get_redirect_uri(request)

    # next URL ko state mein pack karo — callback ke baad wapas jaane ke liye
    import urllib.parse
    params = urllib.parse.urlencode({
        "client_id":     GOOGLE_CLIENT_ID,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         next,
        "access_type":   "online",
        "prompt":        "select_account",
    })
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{params}")


# ── Step 2: Google callback — token exchange + customer upsert ──
@router.get("/auth/google/callback")
async def google_callback(request: Request, code: str = None, state: str = "/", error: str = None):
    """Google callback — code exchange, customer create/fetch, cookie set"""

    if error or not code:
        # User ne cancel kiya ya error — login page pe wapas
        return RedirectResponse(url="/login?error=google_cancelled")

    redirect_uri = get_redirect_uri(request)

    # Code → Access token exchange
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri":  redirect_uri,
            "grant_type":    "authorization_code",
        })

    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Google token exchange failed")

    tokens      = token_resp.json()
    access_token = tokens.get("access_token")

    # Access token se user info fetch karo
    async with httpx.AsyncClient() as client:
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch Google user info")

    userinfo  = userinfo_resp.json()
    google_id = userinfo.get("sub")
    name      = userinfo.get("name", "")
    email     = userinfo.get("email", "")
    picture   = userinfo.get("picture", "")

    if not google_id:
        raise HTTPException(status_code=400, detail="Invalid Google response")

    # DB mein customer upsert karo
    customer = get_or_create_customer(google_id, name, email, picture)

    # Customer JWT token banao
    token = create_token({
        "sub":         str(customer["id"]),
        "role":        "customer",
        "name":        customer["name"],
        "email":       customer["email"],
        "customer_id": customer["id"],
    }, "customer")

    # Profile complete hai ya nahi check karo
    profile_complete = bool(customer.get("phone") and customer.get("address"))

    # next URL — state se
    next_url = state if state and state.startswith("/") else "/"

    if not profile_complete:
        # Phone + address collect karna hai pehle
        # next URL encode karke profile page pe bhejo
        import urllib.parse
        next_encoded = urllib.parse.quote(next_url)
        redirect_to = f"/customer/profile?next={next_encoded}"
    else:
        redirect_to = next_url

    response = RedirectResponse(url=redirect_to)
    response.set_cookie(
        key="customer_token",
        value=token,
        httponly=True,
        max_age=60 * 60 * 24 * 30,   # 30 din
        samesite="lax",
        secure=os.environ.get("IS_PROD", "false").lower() == "true",
    )
    return response


# ── Customer logout ──
@router.get("/auth/customer/logout")
async def customer_logout(request: Request):
    next_url = request.query_params.get("next", "/")
    response = RedirectResponse(url=next_url)
    response.delete_cookie("customer_token")
    return response


# ── Current customer info API ──
@router.get("/api/customer/me")
async def customer_me(request: Request):
    """JS se current customer info fetch karo — token silently refresh bhi hoga"""
    token = request.cookies.get("customer_token")
    if not token:
        return JSONResponse({"logged_in": False})

    from auth import decode_token
    payload = decode_token(token)
    if not payload or payload.get("role") != "customer":
        return JSONResponse({"logged_in": False})

    customer = get_customer_by_id(payload["customer_id"])
    if not customer:
        return JSONResponse({"logged_in": False})

    # ── Sliding expiry — har call pe token renew ──
    new_token = create_token({
        "sub":         str(customer["id"]),
        "role":        "customer",
        "name":        customer["name"],
        "email":       customer["email"],
        "customer_id": customer["id"],
    }, "customer")

    response = JSONResponse({
        "logged_in":        True,
        "id":               customer["id"],
        "name":             customer["name"],
        "email":            customer["email"],
        "picture":          customer.get("picture"),
        "phone":            customer.get("phone"),
        "address":          customer.get("address"),
        "profile_complete": bool(customer.get("phone") and customer.get("address")),
    })
    response.set_cookie(
        key="customer_token",
        value=new_token,
        httponly=True,
        max_age=60 * 60 * 24 * 30,   # 30 din — har visit pe renew
        samesite="lax",
        secure=os.environ.get("IS_PROD", "false").lower() == "true",
    )
    return response


# ── Profile complete karo (phone + address) ──
@router.post("/api/customer/profile")
async def save_customer_profile(request: Request):
    """First time phone + address save karo"""
    token = request.cookies.get("customer_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")

    from auth import decode_token
    payload = decode_token(token)
    if not payload or payload.get("role") != "customer":
        raise HTTPException(status_code=401, detail="Invalid token")

    from db import update_customer_profile
    body = await request.json()
    phone   = body.get("phone", "").strip()
    address = body.get("address", "").strip()

    if not phone or not address:
        raise HTTPException(status_code=400, detail="Phone aur address dono required hain")

    update_customer_profile(payload["customer_id"], phone, address)
    return JSONResponse({"ok": True})


# ── Customer order history ──
@router.get("/api/customer/orders")
async def customer_orders(request: Request):
    """Customer ki delivery order history"""
    token = request.cookies.get("customer_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")

    from auth import decode_token
    payload = decode_token(token)
    if not payload or payload.get("role") != "customer":
        raise HTTPException(status_code=401, detail="Invalid token")

    from db import get_customer_orders
    orders = get_customer_orders(payload["customer_id"])
    return JSONResponse({"orders": orders})
