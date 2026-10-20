from fastapi import FastAPI

app = FastAPI(title="Bid Risk Manager")


@app.get("/health")
def health():
    return {"status": "ok"}