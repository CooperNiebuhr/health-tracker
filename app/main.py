from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return "<html><body><h1>Health Tracker is up</h1></body></html>"