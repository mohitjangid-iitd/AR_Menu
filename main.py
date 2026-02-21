import json
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates

# docs=None, redoc_url=None → disables /docs and /redoc completely
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

templates = Jinja2Templates(directory="templates")

# Allowed asset extensions that the AR/frontend actually needs
ALLOWED_EXTENSIONS = {".glb", ".mind", ".png", ".jpg", ".jpeg", ".webp"}

# Protected extensions — Referer check lagega, direct URL se nahi milega
PROTECTED_EXTENSIONS = {".glb", ".mind"}

def get_client_data(client_id: str):
    file_path = f"data/{client_id}.json"
    if not os.path.exists(file_path):
        return None
    with open(file_path, "r") as f:
        return json.load(f)

@app.get("/static/assets/{client_id}/{filename}")
async def serve_asset(request: Request, client_id: str, filename: str):
    """
    Controlled asset serving:
    - Only whitelisted extensions allowed
    - No directory traversal
    - Client folder must match a valid client
    - GLB/mind files: Referer check — sirf site se load ho, direct URL se nahi
    """
    # Block path traversal attempts
    if ".." in client_id or ".." in filename or "/" in filename:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Only serve whitelisted file types
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=403, detail="File type not allowed")

    # Client must exist
    if not get_client_data(client_id):
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # --- Referer check for protected files (GLB, mind) ---
    if ext in PROTECTED_EXTENSIONS:
        referer = request.headers.get("referer", "")
        host = request.headers.get("host", "")
        if not referer or host not in referer:
            raise HTTPException(status_code=403, detail="Direct access not allowed")

    file_path = f"static/assets/{client_id}/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Asset not found")

    response = FileResponse(file_path)

    if ext in PROTECTED_EXTENSIONS:
        response.headers["Content-Disposition"] = "inline"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"

    return response

@app.get("/{client_id}", response_class=HTMLResponse)
async def restaurant_home(request: Request, client_id: str):
    """Restaurant's home/landing page"""
    data = get_client_data(client_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return templates.TemplateResponse("home.html", {
        "request": request,
        "client_id": client_id,
        "data": data
    })

@app.get("/{client_id}/menu", response_class=HTMLResponse)
async def menu(request: Request, client_id: str):
    """Full menu page"""
    data = get_client_data(client_id)
    if not data:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return templates.TemplateResponse("menu.html", {
        "request": request,
        "client_id": client_id,
        "data": data
    })

@app.get("/{client_id}/ar-menu", response_class=HTMLResponse)
async def ar_menu(request: Request, client_id: str):
    """AR Menu experience page"""
    if not get_client_data(client_id):
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return templates.TemplateResponse("ar_menu.html", {
        "request": request,
        "client_id": client_id
    })

@app.get("/api/menu/{client_id}")
async def get_menu_api(client_id: str):
    """API endpoint for menu data"""
    data = get_client_data(client_id)
    if data:
        return JSONResponse(content=data)
    raise HTTPException(status_code=404, detail="Data not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)