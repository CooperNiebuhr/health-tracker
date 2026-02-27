from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

from app.db import daily_series, get_day_flags, get_weight_entry, init_db, insert_weight_entry, list_weight_entries, restore_weight_entry, soft_delete_weight_entry, update_weight_entry, upsert_day_flags

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

CHI = ZoneInfo("America/Chicago")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    flags_date = datetime.now(CHI).date().isoformat()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "default_range": "30d", "flags_date": flags_date},
    )


@app.get("/partials/history", response_class=HTMLResponse)
def history_partial(request: Request, range: str = "30d"):
    entries = list_weight_entries(range_key=range)
    return templates.TemplateResponse(
        "partials/history.html",
        {"request": request, "entries": entries, "range_key": range},
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
        {"request": request, "entries": entries, "range_key": range},
    )

@app.get("/partials/entry/{entry_id}", response_class=HTMLResponse)
def entry_row(request: Request, entry_id: int, range: str = "30d"):
    e = get_weight_entry(entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse(
        "partials/history_row.html",
        {"request": request, "e": e, "range_key": range},
    )


@app.get("/partials/entry/{entry_id}/edit", response_class=HTMLResponse)
def entry_row_edit(request: Request, entry_id: int, range: str = "30d"):
    e = get_weight_entry(entry_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Not found")

    dt = datetime.fromisoformat(e["entry_ts"])
    entry_time = dt.strftime("%H:%M")

    return templates.TemplateResponse(
        "partials/history_row_edit.html",
        {
            "request": request,
            "e": e,
            "entry_date": e["entry_date"],
            "entry_time": entry_time,
            "range_key": range,
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
        {"request": request, "e": e2, "range_key": range},
    )


@app.delete("/entries/{entry_id}", response_class=HTMLResponse)
def delete_entry(request: Request, entry_id: int, range: str = "30d"):
    soft_delete_weight_entry(entry_id)

    entries = list_weight_entries(range_key=range)

    # Return updated history + an out-of-band toast update
    history_html = templates.get_template("partials/history.html").render(
        request=request,
        entries=entries,
    )
    toast_html = templates.get_template("partials/toast_undo.html").render(
        request=request,
        entry_id=entry_id,
        range=range,
    )

    # hx-swap-oob updates #toast without it being the target
    return HTMLResponse(
        history_html
        + f'<div id="toast" hx-swap-oob="innerHTML">{toast_html}</div>'
    )


@app.post("/entries/{entry_id}/undo", response_class=HTMLResponse)
def undo_delete(request: Request, entry_id: int, range: str = "30d"):
    restore_weight_entry(entry_id)

    entries = list_weight_entries(range_key=range)
    history_html = templates.get_template("partials/history.html").render(
        request=request,
        entries=entries,
    )

    # Clear toast
    return HTMLResponse(
        history_html
        + '<div id="toast" hx-swap-oob="innerHTML"></div>'
    )


@app.get("/api/series", response_class=JSONResponse)
def api_series(range: str = "30d"):
    return daily_series(range_key=range)

@app.get("/partials/day_flags", response_class=HTMLResponse)
def day_flags_partial(request: Request, date: str):
    row = get_day_flags(date)
    did_workout = int(row["did_workout"]) if row else 0
    did_walk = int(row["did_walk"]) if row else 0

    return templates.TemplateResponse(
        "partials/day_flags.html",
        {
            "request": request,
            "date": date,
            "did_workout": did_workout,
            "did_walk": did_walk,
        },
    )


@app.post("/day/{date}/activity", response_class=HTMLResponse)
def set_day_activity(
    request: Request,
    date: str,
    did_workout: int = Form(0),
    did_walk: int = Form(0),
):
    upsert_day_flags(entry_date=date, did_workout=did_workout, did_walk=did_walk)

    # Return updated partial + trigger graph refresh (client JS listens)
    row = get_day_flags(date)
    html = templates.get_template("partials/day_flags.html").render(
        request=request,
        date=date,
        did_workout=int(row["did_workout"]) if row else 0,
        did_walk=int(row["did_walk"]) if row else 0,
    )
    return HTMLResponse(html, headers={"HX-Trigger": "flagsChanged"})


@app.get("/partials/history", response_class=HTMLResponse)
def history_partial(request: Request, range: str = "30d"):
    entries = list_weight_entries(range_key=range)
    return templates.TemplateResponse(
        "partials/history.html",
        {"request": request, "entries": entries, "range_key": range},
    )