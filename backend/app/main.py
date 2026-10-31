from fastapi import FastAPI

app = FastAPI(
    title="Retail AI Data Analytics",
    description="A FastAPI application for Retail AI Data Analytics",
    version="1.0.0",
)


@app.get("/health", tags=["Health Check"])
def health_check():
    return {"status": "healthy"}