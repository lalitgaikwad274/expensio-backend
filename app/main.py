from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter
from app.database import create_tables
from app.routers.auth import router as auth_router
from app.routers.transactions import router as transactions_router
from app.routers.bank_accounts import router as bank_accounts_router



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