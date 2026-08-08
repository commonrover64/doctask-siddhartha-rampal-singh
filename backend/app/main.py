from fastapi import FastAPI

app = FastAPI(title="Loan File Intelligence System")

@app.get("/health")
async def health():
    return {
        "status": "ok"
    }