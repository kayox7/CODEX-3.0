import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.db import init_db
from app.seed import seed_database
from app.api import auth, agents, ledger, reports, actions, approvals, connections
from app.services import approval_service

async def periodic_sla_checker():
    """Background worker to escalate expired approvals and enforce fail-closed SLA timeouts."""
    while True:
        try:
            await asyncio.sleep(settings.ESCALATION_CHECK_INTERVAL_SECONDS)
            approval_service.check_and_escalate_approvals()
        except asyncio.CancelledError:
            break
        except Exception as e:
            # Keep worker running across transient errors
            print(f"[WARDEN SLA] Worker error: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure schema and initial demo seed
    init_db()
    seed_database()
    sla_task = asyncio.create_task(periodic_sla_checker())
    try:
        yield
    finally:
        sla_task.cancel()

app = FastAPI(
    title="WARDEN Governance OS",
    description="Pre-execution control layer between AI agents and enterprise systems",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(ledger.router)
app.include_router(reports.router)
app.include_router(actions.router)
app.include_router(approvals.router)
app.include_router(connections.router)

@app.get("/")
def root():
    return {
        "system": "WARDEN",
        "description": "AI Agent Governance & Human Accountability Operating System",
        "status": "OPERATIONAL",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    is_dev = settings.ENVIRONMENT.lower() in ("development", "dev", "local", "test")
    return {"status": "ok", "environment": settings.ENVIRONMENT, "dev_mode": is_dev}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
