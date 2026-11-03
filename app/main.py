import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import converter, compressor, background_remover, common
from app.services.file_manager import FileManager

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    settings.init_directories()
    FileManager.cleanup_old_files()
    yield
    logger.info("Shutting down Local Image Toolkit")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Self-hosted, offline-first image converter, compressor, and AI background remover.",
    lifespan=lifespan,
)

# Security & CORS configuration (default to local requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and templates
static_dir = Path(__file__).resolve().parent / "static"
templates_dir = Path(__file__).resolve().parent / "templates"

static_dir.mkdir(parents=True, exist_ok=True)
templates_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Include routers
app.include_router(converter.router)
app.include_router(compressor.router)
app.include_router(background_remover.router)
app.include_router(common.router)

@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "max_upload_mb": settings.MAX_UPLOAD_SIZE_MB,
            "convert_formats": settings.SUPPORTED_CONVERT_FORMATS,
            "compress_formats": settings.SUPPORTED_COMPRESS_FORMATS,
        },
    )

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    ico_path = static_dir / "assets" / "favicon.ico"
    if ico_path.exists():
        return FileResponse(ico_path)
    return JSONResponse({"error": "favicon not found"}, status_code=404)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status": "error"},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}", "status": "error"},
    )
