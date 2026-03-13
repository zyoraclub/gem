from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import products
from app.routers import integrations
from app.routers import automation
from app.routers import stats
from app.routers import gem_automation
from app.routers import price_monitor
from app.routers import auth
from app.database import init_db
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize database
    init_db()
    print("Database initialized")
    yield
    # Shutdown
    print("Shutting down")


app = FastAPI(
    title="GEM Portal Automation",
    description="Automation for scraping and uploading products to GEM (Government e-Marketplace)",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth routes (no prefix, uses /api/auth internally)
app.include_router(auth.router)
app.include_router(products.router, prefix="/api", tags=["products"])
app.include_router(integrations.router, prefix="/api", tags=["integrations"])
app.include_router(automation.router, prefix="/api/automation", tags=["automation"])
app.include_router(stats.router, tags=["stats"])
app.include_router(gem_automation.router, tags=["gem-automation"])
app.include_router(price_monitor.router, tags=["price-monitor"])


@app.get("/")
def root():
    return {"message": "GEM Portal Automation API", "status": "running"}
