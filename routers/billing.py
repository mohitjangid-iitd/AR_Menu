"""
routers/billing.py — ZenTable subscription billing API
Sirf admin access — sab routes /api/billing/... pe hain
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from auth import decode_token
from billing_db import (
    # plans
    get_all_plans, get_plan, update_plan,
    # addons
    get_all_addons, get_addon, update_addon,
    # subscriptions
    get_subscription, get_all_subscriptions,
    create_subscription, update_subscription,
    # addons per restaurant
    get_subscription_addons, upsert_subscription_addon, remove_subscription_addon,
    # payments
    confirm_payment, get_payment_history, generate_reference_id,
    # pricing
    calc_price, PERIOD_MULTIPLIER,
    # cron
    run_daily_billing_cron,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])


# ════════════════════════════════
# AUTH HELPER
# ════════════════════════════════

def _require_admin(request: Request) -> dict:
    token = request.cookies.get("auth_token")
    user  = decode_token(token) if token else None
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ════════════════════════════════
# PLANS
# ════════════════════════════════

@router.get("/plans")
async def api_get_plans(request: Request):
    _require_admin(request)
    return get_all_plans()


@router.patch("/plans/{key}")
async def api_update_plan(key: str, request: Request):
    _require_admin(request)
    body = await request.json()
    update_plan(key, body)
    return get_plan(key)


# ════════════════════════════════
# ADDONS
# ════════════════════════════════

@router.get("/addons")
async def api_get_addons(request: Request):
    _require_admin(request)
    return get_all_addons()


@router.patch("/addons/{key}")
async def api_update_addon(key: str, request: Request):
    _require_admin(request)
    body = await request.json()
    update_addon(key, body)
    return get_addon(key)


# ════════════════════════════════
# SUBSCRIPTIONS
# ════════════════════════════════

@router.get("/subscriptions")
async def api_get_all_subscriptions(request: Request):
    """Saari restaurants ki subscription info — admin overview"""
    _require_admin(request)
    subs = get_all_subscriptions()
    # Plans info bhi saath mein bhejo (frontend ko dropdown ke liye chahiye)
    plans  = get_all_plans()
    addons = get_all_addons()
    return {"subscriptions": subs, "plans": plans, "addons": addons}


@router.get("/subscriptions/{client_id}")
async def api_get_subscription(client_id: str, request: Request):
    _require_admin(request)
    sub = get_subscription(client_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    addons  = get_subscription_addons(client_id)
    history = get_payment_history(client_id)
    ref_id  = generate_reference_id(client_id)
    return {
        "subscription": sub,
        "addons":        addons,
        "history":       history,
        "ref_id":        ref_id,
    }


@router.post("/subscriptions/{client_id}")
async def api_create_subscription(client_id: str, request: Request):
    """
    Naya subscription create karo — restaurant onboarding pe.
    Body:
      status: demo | trial | active
      plan_key: basic | pro | elite
      period: monthly | halfyearly | yearly   (active ke liye)
      months: 1                                (active ke liye, default 1)
      discount_percent: 0
      discount_flat: 0
      admin_notes: ""
    """
    _require_admin(request)
    body = await request.json()

    status = body.get("status", "trial")
    if status not in ("demo", "trial", "active"):
        raise HTTPException(status_code=400, detail="Invalid status")

    sub = create_subscription(
        client_id        = client_id,
        status           = status,
        plan_key         = body.get("plan_key", "basic"),
        period           = body.get("period", "monthly"),
        discount_percent = int(body.get("discount_percent", 0)),
        discount_flat    = int(body.get("discount_flat", 0)),
        months           = int(body.get("months", 1)),
        admin_notes      = body.get("admin_notes"),
    )
    return sub


@router.patch("/subscriptions/{client_id}")
async def api_update_subscription(client_id: str, request: Request):
    """
    Subscription update — plan change, discount, dates, notes, etc.
    Sirf jo fields bhejo wo update honge.
    """
    _require_admin(request)
    sub = get_subscription(client_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    body    = await request.json()
    updated = update_subscription(client_id, body)
    return updated


# ════════════════════════════════
# ADDON MANAGEMENT PER RESTAURANT
# ════════════════════════════════

@router.post("/subscriptions/{client_id}/addons")
async def api_add_addon(client_id: str, request: Request):
    """
    Restaurant ko addon add/update karo.
    Body:
      addon_key: ar_menu | kitchen_tab | attendance
      period: monthly | halfyearly | yearly
      discount_percent: 0
      discount_flat: 0
      ends_at: null  (optional override)
    """
    _require_admin(request)
    body = await request.json()
    addon_key = body.get("addon_key")
    if not addon_key:
        raise HTTPException(status_code=400, detail="addon_key required")

    prices = upsert_subscription_addon(
        client_id        = client_id,
        addon_key        = addon_key,
        period           = body.get("period", "monthly"),
        discount_percent = int(body.get("discount_percent", 0)),
        discount_flat    = int(body.get("discount_flat", 0)),
        ends_at          = body.get("ends_at"),
    )
    return {"addon_key": addon_key, **prices}


@router.delete("/subscriptions/{client_id}/addons/{addon_key}")
async def api_remove_addon(client_id: str, addon_key: str, request: Request):
    _require_admin(request)
    remove_subscription_addon(client_id, addon_key)
    return {"ok": True}


# ════════════════════════════════
# PAYMENTS
# ════════════════════════════════

@router.get("/subscriptions/{client_id}/history")
async def api_payment_history(client_id: str, request: Request):
    _require_admin(request)
    return get_payment_history(client_id)


@router.post("/subscriptions/{client_id}/confirm-payment")
async def api_confirm_payment(client_id: str, request: Request):
    """
    Admin manually payment confirm kare.
    Body:
      amount: 1499
      period: monthly | halfyearly | yearly
      payment_mode: upi | cash | bank_transfer
      reference_id: ZT-SPICE-JUN26   (optional, auto-generate hoga)
      notes: ""
    """
    admin = _require_admin(request)
    sub   = get_subscription(client_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    body   = await request.json()
    amount = body.get("amount")
    period = body.get("period", sub.get("period", "monthly"))

    if not amount:
        raise HTTPException(status_code=400, detail="amount required")

    ref = body.get("reference_id") or generate_reference_id(client_id)

    result = confirm_payment(
        client_id    = client_id,
        amount       = int(amount),
        period       = period,
        payment_mode = body.get("payment_mode", "upi"),
        reference_id = ref,
        confirmed_by = admin.get("sub", "admin"),
        notes        = body.get("notes"),
    )
    return result


# ════════════════════════════════
# PRICE PREVIEW
# ════════════════════════════════

@router.get("/preview-price")
async def api_preview_price(
    request:          Request,
    plan_key:         str = "basic",
    period:           str = "monthly",
    discount_percent: int = 0,
    discount_flat:    int = 0,
    addon_keys:       str = "",         # comma-separated: "ar_menu,attendance"
):
    """
    Admin ko real-time price preview — modal mein live update ke liye.
    Returns breakdown: plan price + each addon + total
    """
    _require_admin(request)

    plan = get_plan(plan_key)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_prices = calc_price(
        plan["monthly_price"], period, discount_percent, discount_flat
    )

    addon_breakdown = []
    addon_total     = 0
    if addon_keys:
        for akey in addon_keys.split(","):
            akey = akey.strip()
            if not akey:
                continue
            addon = get_addon(akey)
            if addon and not addon["one_time_only"]:
                ap = calc_price(addon["monthly_price"], period, 0, 0)
                addon_breakdown.append({
                    "key":         akey,
                    "name":        addon["name"],
                    "base_price":  ap["base_price"],
                    "final_price": ap["final_price"],
                })
                addon_total += ap["final_price"]

    return {
        "plan":          plan_prices,
        "addons":        addon_breakdown,
        "addon_total":   addon_total,
        "grand_total":   plan_prices["final_price"] + addon_total,
        "period":        period,
        "multiplier":    PERIOD_MULTIPLIER.get(period, 1),
    }


# ════════════════════════════════
# UPI QR DATA
# ════════════════════════════════

@router.get("/subscriptions/{client_id}/upi-data")
async def api_upi_data(client_id: str, request: Request):
    """
    Payment ke liye UPI string generate karo.
    Frontend isko QR library se render karega.
    upi://pay?pa=...&pn=ZenTable&am=XXXX&tn=ZT-ID-MON26
    """
    _require_admin(request)

    sub = get_subscription(client_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    import os
    upi_id  = os.environ.get("ZENTABLE_UPI_ID", "zentable@upi")
    amount  = sub["final_price"]
    ref_id  = generate_reference_id(client_id)

    upi_str = (
        f"upi://pay?pa={upi_id}"
        f"&pn=ZenTable"
        f"&am={amount}"
        f"&cu=INR"
        f"&tn={ref_id}"
    )

    return {
        "upi_string":  upi_str,
        "upi_id":      upi_id,
        "amount":      amount,
        "reference_id": ref_id,
        "client_id":   client_id,
    }


# ════════════════════════════════
# MANUAL CRON TRIGGER (admin only)
# ════════════════════════════════

@router.post("/run-cron")
async def api_run_cron(request: Request):
    """Manual cron trigger — testing ke liye ya emergency mein"""
    _require_admin(request)
    run_daily_billing_cron()
    return {"ok": True, "message": "Billing cron executed"}
