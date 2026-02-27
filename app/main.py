from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.db import init_db

app = FastAPI()


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return "<html><body><h1>Health Tracker is up</h1></body></html>"