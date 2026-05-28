"""
routers/pages.py — Public + Staff HTML page routes

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
  GET /{client_id}/staff/counter
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Request

from database import get_table_status, get_summary, get_analytics, get_restaurant_branches
from helpers import (
    get_client_data, require_auth,
    is_restaurant_active, closed_response, require_feature, has_feature,
)
from r2 import USE_R2, IS_PROD, r2_public_url
from site_config import SITE_CONFIG
from templates_env import templates

router = APIRouter()
def _block_on_admin_subdomain(request: Request):
    if IS_PROD and request.headers.get("host") == "admin.zentable.in":
        raise HTTPException(status_code=404)

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
    from database import get_customer_by_id
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
    from database import get_customer_by_id
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


@router.get("/{client_id}/table/{table_no}", response_class=HTMLResponse)
async def table_home(request: Request, client_id: str, table_no: int,
                     branch_id: Optional[str] = "__default__"):
    _block_on_admin_subdomain(request)
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
                     branch_id: Optional[str] = "__default__"):
    _block_on_admin_subdomain(request)
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
                        branch_id: Optional[str] = "__default__"):
    _block_on_admin_subdomain(request)
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
