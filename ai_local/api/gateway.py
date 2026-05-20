from fastapi import FastAPI

app = FastAPI(title="AI Local Infrastructure")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

