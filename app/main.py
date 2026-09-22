from fastapi import FastAPI, APIRouter
from app.routers.auth import router as auth_router

app = FastAPI(
    title="Expensio API",
    description="Backend API for Expensio Expense Manager",
    version="1.0.0",
)

api_router = APIRouter(prefix="/api/v1")


app.include_router(api_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {
        "message": "Welcome to Expensio API",
        "status": "running",
    }