from fastapi import FastAPI

app = FastAPI(title="ensight-backend")


@app.get("/")
async def root():
    return {"message": "Hello from ensight-backend!"}


@app.get("/health")
async def health():
    return {"status": "ok"}
