"""
routers/pages.py — Public + Staff HTML page routes

Customer (auth required):
  GET /customer/profile
  GET /customer/orders

Public:
  GET /{client_id}
  GET /{client_id}/menu
  GET /{client_id}/ar-menu
  GET /{client_id}/table/{table_no}
  GET /{client_id}/table/{table_no}/menu
  GET /{client_id}/table/{table_no}/ar-menu

Staff (auth required):
  GET /{client_id}/staff/owner
  GET /{client_id}/staff/kitchen
  GET /{client_id}/staff/waiter
  GET /{client_id}/staff/delivery
  GET /{client_id}/staff/counter
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request

from db import get_table_status, get_summary, get_analytics, get_restaurant_branches
from helpers import (
    get_client_data, require_auth,
    is_restaurant_active, closed_response, require_feature, has_feature,
)
from r2 import USE_R2, IS_PROD, r2_public_url
from site_config import SITE_CONFIG
from templates_env import templates
from auth import decode_table_token, verify_table_token

router = APIRouter()
def _block_on_admin_subdomain(request: Request):
    if IS_PROD and request.headers.get("host") == "admin.zentable.in":
        raise HTTPException(status_code=404)

# ════════════════════════════════
# LEGAL PAGES
# ════════════════════════════════

@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request, "site": SITE_CONFIG})

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request, "site": SITE_CONFIG})

# ════════════════════════════════
# CUSTOMER PAGES
# ════════════════════════════════

@router.get("/customer/profile", response_class=HTMLResponse)
async def customer_profile(request: Request, next: Optional[str] = "/"):
    """Customer phone + address fill karne ka page — pehli baar login ke baad"""
    from auth import decode_token
    token = request.cookies.get("customer_token")
    if not token:
        return RedirectResponse(url=f"/auth/google?next={next}")
    payload = decode_token(token)
    if not payload or payload.get("role") != "customer":
        return RedirectResponse(url=f"/auth/google?next={next}")
    from db import get_customer_by_id
    customer = get_customer_by_id(payload["customer_id"])
    if not customer:
        return RedirectResponse(url=f"/auth/google?next={next}")
    return templates.TemplateResponse("customer_profile.html", {
        "request":  request,
        "customer": customer,
        "next":     next,
        "site":     SITE_CONFIG,
    })


@router.get("/customer/orders", response_class=HTMLResponse)
async def customer_orders_page(request: Request, next: Optional[str] = "/"):
    """Customer ki delivery order history"""
    from auth import decode_token
    token = request.cookies.get("customer_token")
    
    import urllib.parse
    next_encoded = urllib.parse.quote(next or "/")
    
    if not token:
        return RedirectResponse(url=f"/auth/google?next=/customer/orders?next={next_encoded}")
    payload = decode_token(token)
    if not payload or payload.get("role") != "customer":
        return RedirectResponse(url=f"/auth/google?next=/customer/orders?next={next_encoded}")
    from db import get_customer_by_id
    customer = get_customer_by_id(payload["customer_id"])
    if not customer:
        return RedirectResponse(url=f"/auth/google?next=/customer/orders?next={next_encoded}")
    return templates.TemplateResponse("customer_orders.html", {
        "request":  request,
        "customer": customer,
        "site":     SITE_CONFIG,
    })


# ════════════════════════════════
# PUBLIC PAGES
# ════════════════════════════════

@router.get("/{client_id}", response_class=HTMLResponse)
async def restaurant_home(request: Request, client_id: str, branch_id: Optional[str] = "__default__"):
    _block_on_admin_subdomain(request)
    data = get_client_data(client_id, branch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not is_restaurant_active(client_id):
        return closed_response(request, data, client_id)
    
    branch_name = None
    if branch_id and branch_id != "__default__":
        branch_name = data.get("restaurant", {}).get("name")
        default_data = get_client_data(client_id)
        if default_data:
            data["restaurant"]["name"] = default_data["restaurant"]["name"]

    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    return templates.TemplateResponse("home.html", {
        "request": request, "client_id": client_id, "data": data, "table_no": None,
        "branch_id": branch_id,
        "branch_name": branch_name,  # ← add
        "features": features,
    })


@router.get("/{client_id}/menu", response_class=HTMLResponse)
async def menu(request: Request, client_id: str, branch_id: Optional[str] = "__default__"):
    _block_on_admin_subdomain(request)
    data = get_client_data(client_id, branch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not is_restaurant_active(client_id):
        return closed_response(request, data, client_id)
    branch_name = None
    if branch_id and branch_id != "__default__":
        branch_name = data.get("restaurant", {}).get("name")
        default_data = get_client_data(client_id)
        if default_data:
            data["restaurant"]["name"] = default_data["restaurant"]["name"]
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    return templates.TemplateResponse("menu.html", {
        "request": request, "client_id": client_id, "data": data, "table_no": None,
        "branch_id": branch_id,
        "branch_name": branch_name,
        "features": features,
    })


@router.get("/{client_id}/ar-menu", response_class=HTMLResponse)
async def ar_menu(request: Request, client_id: str, branch_id: Optional[str] = "__default__"):
    _block_on_admin_subdomain(request)
    data = get_client_data(client_id, branch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not is_restaurant_active(client_id):
        return closed_response(request, data, client_id)
    if not has_feature(client_id, "ar_menu"):
        qs = f"?branch_id={branch_id}" if branch_id != "__default__" else ""
        return RedirectResponse(url=f"/{client_id}/menu{qs}")
    mind_url = r2_public_url(f"{client_id}/targets.mind") if USE_R2 \
               else f"/static/assets/{client_id}/targets.mind"
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    return templates.TemplateResponse("ar_menu.html", {
        "request": request, "client_id": client_id, "table_no": None,
        "branch_id": branch_id,
        "mind_url": mind_url,
        "features": features,
    })

def check_table_security(request: Request, client_id: str, table_no: int, sig: Optional[str] = None):
    cookie_name = f"table_session_{client_id}"
    branch_id = request.query_params.get("branch_id", "__default__")
    
    if sig:
        if verify_table_token(sig, client_id, table_no, branch_id):
            query_params = dict(request.query_params)
            query_params.pop("sig", None)
            import urllib.parse
            query_string = urllib.parse.urlencode(query_params)
            redirect_url = request.url.path
            if query_string:
                redirect_url += "?" + query_string
                
            response = RedirectResponse(url=redirect_url, status_code=303)
            response.set_cookie(
                key=cookie_name, value=sig, max_age=30*60, httponly=True, secure=True, samesite="Lax"
            )
            return response

    table_session = request.cookies.get(cookie_name)
    if table_session:
        # Check current table
        if verify_table_token(table_session, client_id, table_no, branch_id):
            return None
            
        # Current table check failed, let's see if cookie has a valid authorized_table
        payload = decode_table_token(table_session)
        if payload and payload.get("table_no"):
            authorized_table = payload.get("table_no")
            
            # Optionally we could fully verify it if we wanted to be strict:
            # if verify_table_token(table_session, client_id, authorized_table, branch_id):
            # But the cookie is relatively secure and the worst they can do is redirect.
            if verify_table_token(table_session, client_id, authorized_table, branch_id):
                parts = request.url.path.strip("/").split("/")
                if len(parts) >= 3 and parts[1] == "table":
                    parts[2] = str(authorized_table)
                    new_path = "/" + "/".join(parts)
                    if request.url.query:
                        new_path += "?" + str(request.url.query)
                    return RedirectResponse(url=new_path, status_code=303)

    return RedirectResponse(url=f"/{client_id}", status_code=303)


@router.get("/{client_id}/table/{table_no}", response_class=HTMLResponse)
async def table_home(request: Request, client_id: str, table_no: int,
                     branch_id: Optional[str] = "__default__",
                     sig: Optional[str] = None):
    _block_on_admin_subdomain(request)
    sec_resp = check_table_security(request, client_id, table_no, sig)
    if sec_resp: return sec_resp
    data = get_client_data(client_id, branch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not is_restaurant_active(client_id):
        return closed_response(request, data, client_id)
    table = get_table_status(client_id, table_no, branch_id)
    if not table or table["status"] == "inactive":
        raise HTTPException(status_code=403, detail="Table not active. Please ask staff.")
    branch_name = None
    if branch_id and branch_id != "__default__":
        branch_name = data.get("restaurant", {}).get("name")
        default_data = get_client_data(client_id)
        if default_data:
            data["restaurant"]["name"] = default_data["restaurant"]["name"]
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    return templates.TemplateResponse("home.html", {
        "request": request, "client_id": client_id, "data": data,
        "table_no": table_no, "branch_id": branch_id,
        "branch_name": branch_name,
        "features": features,
    })


@router.get("/{client_id}/table/{table_no}/menu", response_class=HTMLResponse)
async def table_menu(request: Request, client_id: str, table_no: int,
                     branch_id: Optional[str] = "__default__",
                     sig: Optional[str] = None):
    _block_on_admin_subdomain(request)
    sec_resp = check_table_security(request, client_id, table_no, sig)
    if sec_resp: return sec_resp
    data = get_client_data(client_id, branch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not is_restaurant_active(client_id):
        return closed_response(request, data, client_id)
    table = get_table_status(client_id, table_no, branch_id)
    if not table or table["status"] == "inactive":
        raise HTTPException(status_code=403, detail="Table not active. Please ask staff.")
    branch_name = None
    if branch_id and branch_id != "__default__":
        branch_name = data.get("restaurant", {}).get("name")
        default_data = get_client_data(client_id)
        if default_data:
            data["restaurant"]["name"] = default_data["restaurant"]["name"]
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    return templates.TemplateResponse("menu.html", {
        "request": request, "client_id": client_id, "data": data,
        "table_no": table_no, "branch_id": branch_id,
        "branch_name": branch_name,
        "features": features,
    })


@router.get("/{client_id}/table/{table_no}/ar-menu", response_class=HTMLResponse)
async def table_ar_menu(request: Request, client_id: str, table_no: int,
                        branch_id: Optional[str] = "__default__",
                        sig: Optional[str] = None):
    _block_on_admin_subdomain(request)
    sec_resp = check_table_security(request, client_id, table_no, sig)
    if sec_resp: return sec_resp
    data = get_client_data(client_id, branch_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    if not is_restaurant_active(client_id):
        return closed_response(request, data, client_id)
    if not has_feature(client_id, "ar_menu"):
        qs = f"?branch_id={branch_id}" if branch_id != "__default__" else ""
        return RedirectResponse(url=f"/{client_id}/table/{table_no}/menu{qs}")
    table = get_table_status(client_id, table_no, branch_id)
    if not table or table["status"] == "inactive":
        raise HTTPException(status_code=403, detail="Table not active. Please ask staff.")
    mind_url = r2_public_url(f"{client_id}/targets.mind") if USE_R2 \
               else f"/static/assets/{client_id}/targets.mind"
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    return templates.TemplateResponse("ar_menu.html", {
        "request": request, "client_id": client_id,
        "table_no": table_no, "branch_id": branch_id,
        "mind_url": mind_url,
        "features": features,
    })


# ════════════════════════════════
# STAFF PAGES
# ════════════════════════════════

@router.get("/{client_id}/staff/owner", response_class=HTMLResponse)
async def staff_owner(request: Request, client_id: str,
                      auth_token: Optional[str] = Cookie(None)):
    _block_on_admin_subdomain(request)
    user = require_auth(auth_token, ["owner", "admin"], client_id)
    data = get_client_data(client_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    branches = get_restaurant_branches(client_id)
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    response = templates.TemplateResponse("staff_owner.html", {
        "request": request, "client_id": client_id, "data": data, "user": user,
        "branch_id": user.get("branch_id") or "__default__",
        "branches": branches,
        "features": features,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@router.get("/{client_id}/staff/kitchen", response_class=HTMLResponse)
async def staff_kitchen(request: Request, client_id: str,
                        auth_token: Optional[str] = Cookie(None)):
    _block_on_admin_subdomain(request)
    user = require_auth(auth_token, ["kitchen", "owner", "admin"], client_id)
    # Feature gate — kitchen_tab addon check
    require_feature(client_id, "kitchen_tab")
    data = get_client_data(client_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    response = templates.TemplateResponse("staff_kitchen.html", {
        "request": request, "client_id": client_id, "data": data, "user": user,
        "branch_id": user.get("branch_id") or "__default__",
        "features": features,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@router.get("/{client_id}/staff/waiter", response_class=HTMLResponse)
async def staff_waiter(request: Request, client_id: str,
                       auth_token: Optional[str] = Cookie(None)):
    _block_on_admin_subdomain(request)
    user = require_auth(auth_token, ["waiter", "owner", "admin"], client_id)
    data = get_client_data(client_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    response = templates.TemplateResponse("staff_waiter.html", {
        "request": request, "client_id": client_id, "data": data, "user": user,
        "branch_id": user.get("branch_id") or "__default__",
        "features": features,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@router.get("/{client_id}/staff/delivery", response_class=HTMLResponse)
async def staff_delivery(request: Request, client_id: str,
                         auth_token: Optional[str] = Cookie(None)):
    _block_on_admin_subdomain(request)
    user = require_auth(auth_token, ["delivery", "owner", "admin"], client_id)
    require_feature(client_id, "delivery")
    data = get_client_data(client_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    response = templates.TemplateResponse("staff_delivery.html", {
        "request": request, "client_id": client_id, "data": data, "user": user,
        "branch_id": user.get("branch_id") or "__default__",
        "site": SITE_CONFIG,
        "features": features,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response


@router.get("/{client_id}/staff/counter", response_class=HTMLResponse)
async def staff_counter(request: Request, client_id: str,
                        auth_token: Optional[str] = Cookie(None)):
    _block_on_admin_subdomain(request)
    user = require_auth(auth_token, ["counter", "owner", "admin"], client_id)
    data = get_client_data(client_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    features = [f for f in ["ar_menu", "ordering", "analytics", "delivery"] if has_feature(client_id, f)]
    response = templates.TemplateResponse("staff_counter.html", {
        "request": request, "client_id": client_id, "data": data, "user": user,
        "branch_id": user.get("branch_id") or "__default__",
        "features": features,
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response
