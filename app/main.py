import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.database import create_tables
from app.routers.auth import router as auth_router
from app.routers.transactions import router as transactions_router
from app.routers.bank_accounts import router as bank_accounts_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="Expensio API",
    description="Backend API for Expensio Expense Manager",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"422 Validation Error on {request.method} {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

api_router = APIRouter(prefix="/api/v1")


app.include_router(api_router)
app.include_router(auth_router)
app.include_router(transactions_router)
app.include_router(bank_accounts_router)

@app.get("/")
def root():
    return {
        "message": "Welcome to Expensio API",
        "status": "running",
    }