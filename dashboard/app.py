"""CruxTrap SOC dashboard.

    uvicorn dashboard.app:app --port 8000          (DATABASE_URL from env)

Read-only over PostgreSQL. All attacker-supplied text is rendered through Jinja2 with
autoescaping on; data handed to JavaScript goes through `tojson`. There is no login:
bind to 127.0.0.1 (the default in docker-compose) until authentication is added.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import queries as Q
from .charts import line_chart

BASE = Path(__file__).parent
DEFAULT_DSN = "postgresql://cruxtrap:cruxtrap@127.0.0.1:55432/cruxtrap"
PAGE = 50
ACTION_COLORS = {"ALLOW": "#3fb950", "DELAY": "#d29922", "FAKE": "#a371f7", "TARPIT": "#db6d28", "BLOCK": "#f85149"}
log = logging.getLogger("dashboard")


# ------------------------------------------------------------------ filters
def fmt_ts(dt: datetime | None) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if dt else "—"


def ago(dt: datetime | None) -> str:
    if not dt:
        return "—"
    s = int((datetime.now(timezone.utc) - dt).total_seconds())
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if s >= size:
            return f"{s // size}{unit} ago"
    return f"{max(s, 0)}s ago"


def duration(sec: float | None) -> str:
    if sec is None:
        return "—"
    sec = int(sec)
    return f"{sec // 3600}h {sec % 3600 // 60}m" if sec >= 3600 else f"{sec // 60}m {sec % 60}s" if sec >= 60 else f"{sec}s"


def num(v, digits: int = 2) -> str:
    if v is None:
        return "—"
    return f"{v:,.{digits}f}" if isinstance(v, float) else f"{v:,}"


def flag(cc: str | None) -> str:
    if not cc or len(cc) != 2 or not cc.isalpha() or cc in ("LO", "PR"):
        return {"LO": "🖥", "PR": "🏠"}.get(cc or "", "🌐")
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())


def heat(value: float | None, lo: float, hi: float, visited: bool = True) -> str:
    """Background for a Q-table cell. Untried actions stay neutral (their 0.0 is the initial
    value, not a learned one); learned positive values shade green, negative ones red."""
    if value is None or not visited:
        return ""
    if value >= 0:
        a = 0.0 if hi <= 0 else 0.08 + 0.62 * value / hi
        return f"background: rgba(63,185,80,{a:.2f})"
    a = 0.0 if lo >= 0 else 0.08 + 0.62 * value / lo
    return f"background: rgba(248,81,73,{a:.2f})"


# --------------------------------------------------------------------- app
def create_app(database_url: str | None = None) -> FastAPI:
    dsn = database_url or os.getenv("DATABASE_URL", DEFAULT_DSN)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        for attempt in range(1, 31):
            try:
                app.state.pool = await Q.create_pool(dsn)
                break
            except (OSError, asyncpg.PostgresError) as e:
                log.warning("database not ready (%s), attempt %d", e, attempt)
                await asyncio.sleep(2)
        else:
            raise RuntimeError("could not connect to PostgreSQL")
        yield
        await app.state.pool.close()

    app = FastAPI(title="CruxTrap", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
    tpl = Jinja2Templates(directory=BASE / "templates")
    tpl.env.filters.update(ts=fmt_ts, ago=ago, duration=duration, num=num, flag=flag, heat=heat)
    tpl.env.globals.update(ACTION_COLORS=ACTION_COLORS, ACTIONS=Q.ACTIONS, CATEGORIES=Q.CATEGORIES, PHASES=Q.PHASES)

    def render(request: Request, name: str, **ctx) -> HTMLResponse:
        return tpl.TemplateResponse(request, name, {"active": name.split(".")[0], **ctx})

    def pool(request: Request) -> asyncpg.Pool:
        return request.app.state.pool

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        # Scripts: same-origin files only (no inline JS anywhere). Styles: inline allowed because bar
        # widths and colours are set via style="--w: …"; those values are numbers/fixed colours, never
        # attacker text, which is always autoescaped element content.
        resp.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                                                   "script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    @app.get("/healthz")
    async def healthz(request: Request):
        await pool(request).fetchval("SELECT 1")
        return {"ok": True}

    @app.get("/api/stats")
    async def api_stats(request: Request):
        return JSONResponse(await Q.stats(pool(request)))

    @app.get("/", response_class=HTMLResponse)
    async def overview(request: Request):
        p = pool(request)
        stats, hourly, users, pwds, cmds, cats, acts, countries, (recent, _) = await asyncio.gather(
            Q.stats(p), Q.sessions_per_hour(p), Q.top(p, "username", "login_attempts"),
            Q.top(p, "password", "login_attempts"), Q.top(p, "command", "session_actions", 10),
            Q.top(p, "category", "session_actions", 10), Q.top(p, "action", "session_actions"),
            Q.top(p, "country", "attackers"), Q.list_sessions(p, limit=10))
        return render(request, "overview.html", stats=stats, hourly=hourly, users=users, pwds=pwds, cmds=cmds,
                      cats=cats, acts=acts, countries=countries, recent=recent)

    @app.get("/sessions", response_class=HTMLResponse)
    async def sessions(request: Request, q: str = "", min_commands: int = Query(0, ge=0), page: int = Query(1, ge=1)):
        rows, total = await Q.list_sessions(pool(request), q.strip(), min_commands, PAGE, (page - 1) * PAGE)
        return render(request, "sessions.html", rows=rows, total=total, q=q, min_commands=min_commands, page=page,
                      pages=max(1, -(-total // PAGE)))

    @app.get("/sessions/{session_id}", response_class=HTMLResponse)
    async def session_detail(request: Request, session_id: str):
        s = await Q.get_session(pool(request), session_id)
        if s is None:
            raise HTTPException(404, "session not found")
        t0 = s["started_at"]
        replay = [{"seq": a["seq"], "t": round((a["ts"] - t0).total_seconds(), 2), "cmd": a["command"],
                   "action": a["action"], "category": a["category"]} for a in s["actions"]]
        return render(request, "session.html", s=s, replay=replay)

    @app.get("/attackers", response_class=HTMLResponse)
    async def attackers(request: Request, q: str = "", page: int = Query(1, ge=1)):
        rows, total = await Q.list_attackers(pool(request), q.strip(), PAGE, (page - 1) * PAGE)
        return render(request, "attackers.html", rows=rows, total=total, q=q, page=page, pages=max(1, -(-total // PAGE)))

    @app.get("/attackers/{ip}", response_class=HTMLResponse)
    async def attacker_detail(request: Request, ip: str):
        a = await Q.get_attacker(pool(request), ip)
        if a is None:
            raise HTTPException(404, "attacker not found")
        return render(request, "attacker.html", a=a)

    @app.get("/rl", response_class=HTMLResponse)
    async def rl(request: Request, bucket: int = Query(20, ge=1, le=1000)):
        p = pool(request)
        table, curve, mix, stats = await asyncio.gather(Q.q_table(p), Q.learning_curve(p, bucket), Q.action_mix(p, bucket), Q.stats(p))
        qvals = [v for row in table.values() for v in row["q"].values()]
        lo, hi = (min(qvals), max(qvals)) if qvals else (0.0, 1.0)
        charts = {
            "engagement": line_chart({"commands / session": [c["commands"] for c in curve]},
                                     {"commands / session": "#58a6ff"}, x_label=f"blocks of {bucket} sessions"),
            "reward": line_chart({"return / session": [c["reward"] for c in curve]},
                                 {"return / session": "#3fb950"}, x_label=f"blocks of {bucket} sessions"),
            "epsilon": line_chart({"epsilon": [c["epsilon"] for c in curve]}, {"epsilon": "#d29922"},
                                  x_label=f"blocks of {bucket} sessions", y_fmt="{:.2f}"),
        }
        for m in mix:
            m["total"] = sum(m[a] for a in Q.ACTIONS) or 1
        return render(request, "rl.html", table=table, lo=lo, hi=hi, charts=charts, mix=mix, bucket=bucket, stats=stats)

    @app.exception_handler(HTTPException)
    async def not_found(request: Request, exc: HTTPException):
        return tpl.TemplateResponse(request, "error.html", {"active": "", "status": exc.status_code, "detail": exc.detail},
                                    status_code=exc.status_code)

    return app


app = create_app()
