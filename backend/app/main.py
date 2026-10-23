from fastapi import FastAPI

app = FastAPI(title="AI Job Chat Assistant")


@app.get("/health")
def health_check():
    return {"status": "ok"}