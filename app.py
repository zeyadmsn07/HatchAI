from fastapi import FastAPI

app = FastAPI(title="HatchAI")


@app.get("/")
def root():
    return {"status": "HatchAI running"}
