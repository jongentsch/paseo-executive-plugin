from __future__ import annotations

import json
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .core import ExecutiveError
from .runtime import get_runtime
from .tools import execute

router = APIRouter()


class Action(BaseModel):
    name: Literal["paseo_hosts", "paseo_spawn", "paseo_agents", "paseo_worker_details", "paseo_permissions", "paseo_decide_permission", "paseo_events", "paseo_subscribe"]
    args: dict = Field(default_factory=dict)
    user_confirmed: bool = False


@router.get("/state")
def state():
    runtime = get_runtime()
    runtime.start()
    store = runtime.store
    with store.db() as db:
        agents = [dict(host_id=r["host"], **json.loads(r["data"])) for r in db.execute(
            "SELECT s.* FROM snapshots s JOIN hosts h ON h.id=s.host ORDER BY s.host,s.agent")]
        latest = db.execute("SELECT coalesce(max(id),0) FROM events").fetchone()[0]
    return {"hosts": store.hosts(), "config_error": runtime.config_error, "agents": agents,
            "events": store.events(after=max(0, latest - 100)),
            "monitor_enabled": store.setting("monitor_enabled", True),
            "notification_session_key": store.setting("notification_session_key")}


@router.post("/action")
def action(body: Action):
    if body.name == "paseo_decide_permission" and not body.user_confirmed:
        raise HTTPException(403, "A direct user decision is required for permission responses")
    runtime = get_runtime()
    runtime.start()
    try:
        return execute(runtime, body.name, body.args)
    except (ExecutiveError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/events")
def events(after: int = 0, limit: int = 100):
    result = get_runtime().store.events(after=after, limit=limit)
    return {"events": result, "next_cursor": result[-1]["id"] if result else after}


@router.get("/workers/{host_id}/{agent_id}/details")
def worker_details(host_id: str, agent_id: str, tail: int = 20, event_id: int | None = None):
    try:
        return get_runtime().executive.details(host_id, agent_id, tail=tail, event_id=event_id)
    except (ExecutiveError, ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
