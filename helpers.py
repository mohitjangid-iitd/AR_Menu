"""
helpers.py — Shared helper functions for route handlers

get_client_data, require_auth, require_feature etc.
main.py se nikala gaya — saare routers yahan se import karenge.
"""

import json
from typing import Optional
from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from database import get_db
from auth import decode_token, get_redirect_url
from site_config import SITE_CONFIG


def get_client_data(client_id: str, branch_id: str = "__default__"):
    """
    DB se restaurant config fetch karo.
    - branch ka config return karta hai
    - theme brand-level se merge hoti hai (sirf __default__ row pe hoti hai)
    - nahi mila toh None
    """
    conn = get_db()

    # Branch-level config
    cur = conn.execute(
        "SELECT config, theme FROM restaurants WHERE client_id=%s AND branch_id=%s",
        (client_id, branch_id)
    )
    row = cur.fetchone()

    # Agar specific branch nahi mili aur __default__ nahi maanga tha
    # toh __default__ try karo (fallback)
    if not row and branch_id != "__default__":
        cur = conn.execute(
            "SELECT config, theme FROM restaurants WHERE client_id=%s AND branch_id='__default__'",
            (client_id,)
        )
        row = cur.fetchone()

    if not row:
        conn.close()
        return None

    config = row["config"] if isinstance(row["config"], dict) else json.loads(row["config"])
    theme = row["theme"]

    # Theme merge karo — theam keval main branch wale theme column me h
    if not theme:
        cur = conn.execute(
            "SELECT theme FROM restaurants WHERE client_id=%s AND branch_id='__default__'",
            (client_id,)
        )
        trow = cur.fetchone()
        if trow and trow["theme"]:
            theme = trow["theme"]

    conn.close()

    if theme:
        config["theme"] = theme if isinstance(theme, dict) else json.loads(theme)

    return config


def has_feature(client_id: str, feature: str) -> bool:
    """
    Restaurant ke liye feature enabled hai ya nahi.
    Naya system: billing_db.has_feature() se check hoga — subscriptions table se.
    Trial/demo mein sab features on hote hain.
    """
    # Feature key mapping to align codebase checks with DB plan feature keys
    mapping = {
        "analytics": "owner_analytics",
        "ordering": "qr_ordering",
        "chatbot": "ai_chatbot",
        "image_to_menu": "ai_menu_import",
    }
    db_feature = mapping.get(feature, feature)
    from billing_db import has_feature as _billing_has_feature
    return _billing_has_feature(client_id, db_feature)


def require_feature(client_id: str, feature: str):
    """Feature nahi hai toh 403"""
    if not has_feature(client_id, feature):
        raise HTTPException(status_code=403, detail=f"Feature '{feature}' not available")


def require_feature_decorator(feature_key: str):
    """
    Route pe feature gate lagao — decorator version.

    Usage:
        @router.get("/owner/analytics")
        @require_feature_decorator("owner_analytics")
        async def analytics(request: Request):
            ...

    - Trial / Demo: sab milta hai (has_feature handles this)
    - Active: sirf plan + addon check
    - Expired: 403
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Request ko args ya kwargs se nikalo
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if hasattr(arg, "cookies"):
                        request = arg
                        break

            if request is None:
                raise HTTPException(status_code=500, detail="Request object not found")

            token = request.cookies.get("auth_token")
            user  = decode_token(token) if token else None
            if not user:
                raise HTTPException(status_code=401, detail="Login required")

            client_id = user.get("client_id")
            if not client_id:
                raise HTTPException(status_code=400, detail="client_id missing in token")

            if not has_feature(client_id, feature_key):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "locked":      True,
                        "feature_key": feature_key,
                        "message":     "Yeh feature aapke plan mein nahi hai. Upgrade karein.",
                    }
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def is_restaurant_active(client_id: str) -> bool:
    """
    Restaurant active hai ya nahi — subscriptions.status se check karo.
    expired = inactive, baaki sab = active.
    Agar subscription nahi hai toh active maano (naye restaurants ke liye).
    """
    from billing_db import get_subscription
    sub = get_subscription(client_id)
    if not sub:
        return True   # subscription nahi hai — default active
    return sub["status"] != "expired"


def closed_response(request, data, client_id):
    return RedirectResponse(url=SITE_CONFIG["instagram"], status_code=302)


def get_current_user(token: Optional[str]) -> Optional[dict]:
    """Cookie token decode karo"""
    if not token:
        return None
    return decode_token(token)


def require_auth(token: Optional[str], allowed_roles: list, client_id: str = None) -> dict:
    """
    Auth check — fail hone pe 302 login redirect.
    client_id dene pe restaurant match bhi check hoga (admin exempt).
    Returns user dict with branch_id guaranteed present.
    """
    user = get_current_user(token)
    if not user:
        login_url = "/admin/login" if allowed_roles == ["admin"] else "/login"
        raise HTTPException(
            status_code=302,
            headers={
                "Location": login_url,
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            }
        )
    if user.get("role") not in allowed_roles:
        raise HTTPException(status_code=403, detail="Access denied")

    if client_id and user.get("role") != "admin":
        # client_id token mein client_id ya legacy restaurant_id key mein ho sakta hai
        user_cid = user.get("client_id") or user.get("restaurant_id")
        if user_cid != client_id:
            raise HTTPException(status_code=403, detail="Access denied — wrong restaurant")

    # branch_id guaranteed hona chahiye — owner ke liye None (all branches)
    if "branch_id" not in user:
        user["branch_id"] = None if user.get("role") == "owner" else "__default__"

    return user
