"""
routers/tables.py — Table management API

POST /api/table/{client_id}/{table_no}/activate
POST /api/table/{client_id}/activate-all
POST /api/table/{client_id}/{table_no}/close
POST /api/table/{client_id}/close-all
GET  /api/tables/{client_id}/summary
GET  /api/tables/{client_id}
GET  /api/table/{client_id}/{table_no}/detail
POST /api/table/{client_id}/{table_no}/call
POST /api/table/{client_id}/{table_no}/call/resolve
GET  /api/tables/{client_id}/calls
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Cookie, Query, Request

from db import (
    activate_table, activate_all_tables,
    close_table, close_all_tables,
    get_all_tables, get_table_summary,
    get_table_orders_detail,
    create_waiter_call, get_active_calls, resolve_waiter_call,
)
from helpers import get_client_data, require_auth, require_feature
from auth import create_table_token
from rate_limit import limiter

router = APIRouter()


@router.post("/api/table/{client_id}/{table_no}/activate")
@limiter.limit("20/minute")
async def api_activate_table(request: Request, client_id: str, table_no: int,
                              auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["waiter", "counter", "owner", "admin"], client_id)
    if not get_client_data(client_id):
        raise HTTPException(status_code=404, detail="Restaurant not found")
    branch_id = user["branch_id"] or "__default__"
    if branch_id != "__default__":
        require_feature(client_id, "multi_branch")
    activate_table(client_id, table_no, branch_id)
    return {"message": f"Table {table_no} activated"}


@router.post("/api/table/{client_id}/activate-all")
@limiter.limit("10/minute")
async def api_activate_all_tables(request: Request, client_id: str,
                                   branch_id: Optional[str] = Query(None),
                                   auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["counter", "owner", "admin"], client_id)
    effective_branch = branch_id or user.get("branch_id") or "__default__"
    if effective_branch != "__default__":
        require_feature(client_id, "multi_branch")
    activate_all_tables(client_id, effective_branch)
    return {"message": "All tables activated"}


@router.post("/api/table/{client_id}/{table_no}/close")
@limiter.limit("20/minute")
async def api_close_table(request: Request, client_id: str, table_no: int,
                           auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["waiter", "counter", "owner", "admin"], client_id)
    branch_id = user["branch_id"] or "__default__"
    close_table(client_id, table_no, branch_id)
    return {"message": f"Table {table_no} closed"}


@router.post("/api/table/{client_id}/close-all")
@limiter.limit("10/minute")
async def api_close_all_tables(request: Request, client_id: str,
                                branch_id: Optional[str] = Query(None),
                                auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["counter", "owner", "admin"], client_id)
    effective_branch = branch_id or user.get("branch_id") or "__default__"
    close_all_tables(client_id, effective_branch)
    return {"message": "All tables closed"}


@router.get("/api/tables/{client_id}/summary")
@limiter.limit("60/minute")
async def api_table_summary(request: Request, client_id: str,
                             branch_id: Optional[str] = Query(None),
                             auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["waiter", "counter", "owner", "admin"], client_id)
    effective_branch = branch_id or user.get("branch_id") or "__default__"
    return get_table_summary(client_id, effective_branch)


@router.get("/api/tables/{client_id}")
async def api_get_tables(client_id: str,
                         branch_id: Optional[str] = Query(None),
                         auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["waiter", "counter", "owner", "admin"], client_id)
    effective_branch = branch_id or user.get("branch_id") or "__default__"
    return get_all_tables(client_id, effective_branch)


@router.get("/api/table/{client_id}/{table_no}/detail")
async def api_table_detail(client_id: str, table_no: int,
                            auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["waiter", "counter", "owner", "admin"], client_id)
    branch_id = user["branch_id"] or "__default__"
    return get_table_orders_detail(client_id, table_no, branch_id)


@router.get("/api/table/{client_id}/{table_no}/qr-sig")
async def api_get_qr_sig(client_id: str, table_no: int,
                          auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["counter", "owner", "admin"], client_id)
    branch_id = user["branch_id"] or "__default__"
    sig = create_table_token(client_id, table_no, branch_id)
    return {"sig": sig}


# ════════════════════════════════
# WAITER CALL ENDPOINTS
# ════════════════════════════════

@router.post("/api/table/{client_id}/{table_no}/call")
@limiter.limit("3/minute")
async def api_call_waiter(request: Request, client_id: str, table_no: int,
                          branch_id: Optional[str] = "__default__"):
    """Customer ne bell dabaya — no auth (public endpoint)
    branch_id query param se aa sakta hai — default __default__
    """
    if not get_client_data(client_id):
        raise HTTPException(status_code=404, detail="Restaurant not found")
    create_waiter_call(client_id, table_no, branch_id)
    return {"message": f"Waiter called for table {table_no}"}


@router.post("/api/table/{client_id}/{table_no}/call/resolve")
async def api_resolve_call(client_id: str, table_no: int,
                           auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["waiter", "counter", "owner", "admin"], client_id)
    if not get_client_data(client_id):
        raise HTTPException(status_code=404, detail="Restaurant not found")
    branch_id = user["branch_id"] or "__default__"
    resolve_waiter_call(client_id, table_no, branch_id)
    return {"message": f"Call resolved for table {table_no}"}


@router.get("/api/tables/{client_id}/calls")
async def api_get_calls(client_id: str,
                        auth_token: Optional[str] = Cookie(None)):
    user = require_auth(auth_token, ["waiter", "counter", "owner", "admin"], client_id)
    branch_id = user["branch_id"] or "__default__"
    return get_active_calls(client_id, branch_id)
