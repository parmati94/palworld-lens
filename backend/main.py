"""FastAPI backend for Palworld Lens"""
import asyncio
import json
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from backend.common.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

from backend.common.config import config
from backend.common.auth import (
    verify_credentials, 
    create_session_token, 
    get_session_from_request,
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE
)
from backend.parser import parser

# Import startup logic and global state
from backend import startup

# Import routers
from backend.routers import debug, api, watch

app = FastAPI(
    title="Palworld Lens",
    description="Read-only viewer for Palworld save files",
    version="1.0.0",
    lifespan=startup.lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(debug.router)
app.include_router(api.router)
app.include_router(watch.router)

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Palworld Lens API", "version": "1.0.0"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "save_loaded": parser.loaded,
        "last_updated": parser.last_load_time.isoformat() if parser.last_load_time else None
    }

# Pydantic models for auth
class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/api/auth/status")
async def auth_status(request: Request):
    """Check if authentication is enabled and if user is logged in"""
    if not config.ENABLE_LOGIN:
        return {"enabled": False, "authenticated": True}
    
    username = get_session_from_request(request)
    return {
        "enabled": True,
        "authenticated": username is not None,
        "username": username if username else None
    }

@app.post("/api/auth/login")
async def login(login_data: LoginRequest, response: Response):
    """Login endpoint"""
    if not config.ENABLE_LOGIN:
        raise HTTPException(status_code=400, detail="Authentication is not enabled")
    
    if not verify_credentials(login_data.username, login_data.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create session token
    token = create_session_token(login_data.username)
    
    # Set cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False  # Set to True if using HTTPS
    )
    
    logger.info(f"User '{login_data.username}' logged in successfully")
    
    return {"success": True, "username": login_data.username}

@app.post("/api/auth/logout")
async def logout(response: Response):
    """Logout endpoint"""
    response.delete_cookie(SESSION_COOKIE_NAME)
    logger.info("User logged out")
    return {"success": True}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info"
    )
