from fastapi import FastAPI, APIRouter

app = FastAPI(
    title="Expensio API",
    description="Backend API for Expensio Expense Manager",
    version="1.0.0",
)

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "expensio-api",
    }


app.include_router(api_router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Expensio API",
        "status": "running",
    }