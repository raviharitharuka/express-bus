from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from errors import register_error_handlers
from routers import dashboard, emergency, idle_drivers, lotse, optimize

app = FastAPI(title="Express Bus Optimizer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

app.include_router(idle_drivers.router)
app.include_router(optimize.router)
app.include_router(emergency.router)
app.include_router(lotse.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}
