from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db import get_weight_entry, init_db, insert_weight_entry, list_weight_entries, update_weight_entry

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

@app.get("/partials/entry/{entry_id}", response_class=HTMLResponse)
def entry_row(request: Request, entry_id: int):
    e = get_weight_entry(entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse(
        "partials/history_row.html",
        {"request": request, "e": e},
    )


@app.get("/partials/entry/{entry_id}/edit", response_class=HTMLResponse)
def entry_row_edit(request: Request, entry_id: int):
    e = get_weight_entry(entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Not found")

    # Parse entry_ts to prefill time (HH:MM)
    dt = datetime.fromisoformat(e["entry_ts"])
    entry_time = dt.strftime("%H:%M")

    return templates.TemplateResponse(
        "partials/history_row_edit.html",
        {
            "request": request,
            "e": e,
            "entry_date": e["entry_date"],
            "entry_time": entry_time,
        },
    )


@app.patch("/entries/{entry_id}", response_class=HTMLResponse)
def patch_entry(
    request: Request,
    entry_id: int,
    entry_date: str = Form(...),
    entry_time: str = Form(...),
    weight_lbs: float = Form(...),
    notes: str | None = Form(None),
):
    e = get_weight_entry(entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Not found")

    dt = datetime.fromisoformat(f"{entry_date}T{entry_time}").replace(tzinfo=CHI)

    update_weight_entry(
        entry_id=entry_id,
        entry_ts=dt.isoformat(timespec="seconds"),
        entry_date=entry_date,
        weight_lbs=weight_lbs,
        notes=(notes.strip() if notes else None),
    )

    # Return the updated view-mode row
    e2 = get_weight_entry(entry_id)
    return templates.TemplateResponse(
        "partials/history_row.html",
        {"request": request, "e": e2},
    )