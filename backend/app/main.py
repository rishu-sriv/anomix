from fastapi import FastAPI

app = FastAPI(title="FinPulse API", version="0.1.0")


@app.get("/api/v1/health")
async def health() -> dict:
    """
    Health check endpoint.
    Phase 0: returns static response.
    Phase 4: will check real DB and Redis connections.
    """
    return {
        "status": "healthy",
        "db": "not_checked",
        "redis": "not_checked",
        "note": "Phase 0 stub — real health check implemented in Phase 4",
    }
