import os, sys
# Đảm bảo import được module gốc của project
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from web.backend.auth import router as auth_router, get_current_user, TokenData
from web.backend.routers.cameras import router as cameras_router
from web.backend.routers.violations import router as violations_router
from web.backend.routers.stats import router as stats_router

app = FastAPI(title="Traffic AI Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ──────────────────────────────────────────
app.include_router(auth_router,       prefix="/api/auth",       tags=["Auth"])
app.include_router(cameras_router,    prefix="/api/cameras",    tags=["Cameras"])
app.include_router(violations_router, prefix="/api/violations", tags=["Violations"])
app.include_router(stats_router,      prefix="/api/stats",      tags=["Stats"])

# ── Mount Evidence folder để xem ảnh bằng chứng ─────────
EVIDENCE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Evidence"
)
if os.path.exists(EVIDENCE_DIR):
    app.mount("/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")

# ── Serve Frontend ───────────────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")
FRONTEND_DIR = os.path.abspath(FRONTEND_DIR)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    filepath = os.path.join(FRONTEND_DIR, full_path)
    if os.path.exists(filepath) and os.path.isfile(filepath):
        return FileResponse(filepath)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
