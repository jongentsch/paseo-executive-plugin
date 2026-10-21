"""Bounded, explicitly unverified context for worker events and follow-up reads."""
from datetime import datetime
import hashlib
import json

MAX_SUMMARY = 2400
MAX_REPORT = 12000


def clipped(value, limit=MAX_SUMMARY):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text[:limit]


def connection_key(host):
    fields = {key: host.get(key) for key in ("home", "target", "stream_url", "password_env")}
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def timestamp(value):
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return None


def report_from_activity(activity):
    result = {"summary": None, "source": activity.get("source", "unavailable"),
              "scope": activity.get("scope", "unknown"), "verification": "not_verified",
              "truncated": bool(activity.get("truncated")), "observed_at": activity.get("observed_at")}
    if activity.get("error"):
        result["unavailable_reason"] = clipped(activity["error"], 500)
        return result
    entries = activity.get("entries") or []
    messages = [entry for entry in entries if entry.get("type") == "assistant_message" and entry.get("text")]
    text = messages[-1]["text"] if messages else activity.get("text")
    if not text:
        result["unavailable_reason"] = "No assistant response in the bounded activity window"
        return result
    result.update(summary=clipped(text), attribution="worker_reported" if messages else "unclassified_activity",
                  truncated=result["truncated"] or len(text) > MAX_SUMMARY)
    if messages:
        result["response_timestamp"] = messages[-1].get("timestamp")
        result["turn_id"] = messages[-1].get("turn_id")
        # Only structured claims are separated; prose is never guessed into test results.
        try:
            claims = json.loads(text)
        except (ValueError, TypeError):
            claims = None
        if isinstance(claims, dict):
            evidence = {}
            for key in ("tests", "changed_files", "artifacts"):
                value = claims.get(key)
                if isinstance(value, list):
                    evidence[key] = [clipped(item, 400) for item in value[:12]]
            if isinstance(claims.get("passed"), bool):
                evidence["reported_passed"] = claims["passed"]
            if evidence:
                result["reported_evidence"] = evidence
            if isinstance(claims.get("summary"), str):
                result["summary"] = clipped(claims["summary"])
    return result


def event_context(host, snapshot, assignment, tracking, observed_at, source):
    worker = {"name": snapshot.get("name"), "provider": snapshot.get("provider"),
              "model": snapshot.get("model"), "cwd": snapshot.get("cwd"),
              "workspace_id": snapshot.get("workspaceId"), "branch": None}
    if assignment:
        for field in ("name", "provider", "cwd"):
            if not worker[field]:
                worker[field] = assignment.get("title" if field == "name" else field)
    worktree = snapshot.get("worktree")
    if isinstance(worktree, dict):
        worker["branch"] = worktree.get("branch") or worktree.get("branchName") or worktree.get("Branch")
    started = tracking.get("started_at")
    return {"host_label": host.get("label") or host["id"], "connection_key": connection_key(host),
            "worker": worker, "assignment": assignment,
            "timing": {"started_at": started, "observed_at": observed_at,
                       "elapsed_seconds": round(max(0, observed_at - started), 3) if started is not None else None,
                       "basis": tracking.get("time_basis", "unknown")},
            "observation": {"source": source, "snapshot_updated_at": snapshot.get("updatedAt"),
                            "turn_id": tracking.get("turn_id"), "sequence": tracking.get("sequence", 0)}}


def public_snapshot(snapshot):
    fields = ("id", "name", "provider", "model", "cwd", "status", "workspaceId", "worktree",
              "createdAt", "updatedAt", "activeTurn", "lastError", "pendingPermissions", "lastUsage")
    return {key: snapshot.get(key) for key in fields if key in snapshot}


def bounded(value, budget=16000):
    """Keep returned JSON valid while bounding nested worker-controlled content."""
    remaining = [budget]
    truncated = [False]
    def visit(item, depth=0):
        if remaining[0] <= 0 or depth > 7:
            truncated[0] = True
            return "[truncated]"
        remaining[0] -= 4
        if isinstance(item, dict):
            result = {}
            for index, (key, value) in enumerate(item.items()):
                if index >= 30 or remaining[0] <= 0:
                    truncated[0] = True
                    break
                remaining[0] -= len(str(key)[:100])
                result[str(key)[:100]] = visit(value, depth + 1)
            return result
        if isinstance(item, list):
            if len(item) > 20:
                truncated[0] = True
            result = []
            for value in item[:20]:
                if remaining[0] <= 0:
                    truncated[0] = True
                    break
                result.append(visit(value, depth + 1))
            return result
        if isinstance(item, str):
            limit = min(4000, remaining[0])
            remaining[0] -= min(len(item), limit)
            if len(item) > limit:
                truncated[0] = True
            return item[:limit]
        return item
    return visit(value), truncated[0]
