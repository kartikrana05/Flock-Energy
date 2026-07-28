from fastapi import Depends, FastAPI

from app.api import admin, auth, consumption, meters, network
from app.security import require_auth

app = FastAPI(
    title="Urja Meter Ops API",
    description="Clean API over the Urja Meter Ops portal.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(meters.router, dependencies=[Depends(require_auth)])
app.include_router(network.router, dependencies=[Depends(require_auth)])
app.include_router(consumption.router, dependencies=[Depends(require_auth)])
app.include_router(admin.router, dependencies=[Depends(require_auth)])
