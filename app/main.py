from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import init_db, insert_weight_entry, list_weight_entries

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

CHI = ZoneInfo("America/Chicago")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "default_range": "30d"},
    )


@app.get("/partials/history", response_class=HTMLResponse)
def history_partial(request: Request, range: str = "30d"):
    entries = list_weight_entries(range_key=range)
    return templates.TemplateResponse(
        "partials/history.html",
        {"request": request, "entries": entries},
    )


@app.post("/entries", response_class=HTMLResponse)
def create_entry(
    request: Request,
    entry_date: str = Form(...),           # YYYY-MM-DD
    entry_time: str | None = Form(None),   # HH:MM (optional)
    weight_lbs: float = Form(...),
    notes: str | None = Form(None),
    range: str = Form("30d"),
):
    # Compute timestamp in America/Chicago
    if entry_time and entry_time.strip():
        dt = datetime.fromisoformat(f"{entry_date}T{entry_time}")
        dt = dt.replace(tzinfo=CHI)
    else:
        now = datetime.now(CHI)
        dt = now.replace(year=int(entry_date[0:4]), month=int(entry_date[5:7]), day=int(entry_date[8:10]))

    insert_weight_entry(
        entry_ts=dt.isoformat(timespec="seconds"),
        entry_date=entry_date,
        weight_lbs=weight_lbs,
        notes=(notes.strip() if notes else None),
    )

    # Return updated history fragment (HTMX swaps it into #history)
    entries = list_weight_entries(range_key=range)
    return templates.TemplateResponse(
        "partials/history.html",
        {"request": request, "entries": entries},
    )