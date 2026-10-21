from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from .core import Executive, ExecutiveError, PLUGIN_ID, PaseoCLI, Store, event_message

log = logging.getLogger(PLUGIN_ID)
_instances = {}
_contexts = {}
_guard = threading.RLock()


def spawn_thread(target, name):
    from agent.memory_provider import spawn_context_thread
    thread = spawn_context_thread(target, name=name)
    thread.start()
    return thread


class Runtime:
    def __init__(self, store, cli=None):
        self.store = store
        self.executive = Executive(store, cli)
        self.owner = str(uuid.uuid4())
        self.stop_event = threading.Event()
        self.workers = {}
        self.processes = {}
        self.context = None
        self.config_error = None
        self.thread = None
        self.lock = threading.RLock()

    def refresh_settings(self):
        """Reconcile the native Settings form into the same registry used by tools/UI."""
        if self.context is None:
            return
        with self.lock:
            configured = self.context.get_config("hosts", None)
            if configured is None:
                return  # Preserve existing plugin-data hosts when upgrading.
            try:
                clean = self.store.validate_hosts(configured)
                if clean != self.store.host_configs():
                    self.store.replace_hosts(clean)
                self.config_error = None
            except (ExecutiveError, ValueError, TypeError) as exc:
                self.config_error = str(exc)

    def save_hosts(self, hosts):
        with self.lock:
            clean = self.store.validate_hosts(hosts)
            # One authoritative settings value; failed persistence leaves live hosts intact.
            if self.context is not None:
                self.context.set_config("hosts", clean)
            self.store.replace_hosts(clean)
            self.config_error = None
        return self.store.hosts()

    def save_host(self, config):
        with self.lock:
            self.refresh_settings()
            clean = self.store.validate_host(config)
            self.save_hosts([h for h in self.store.host_configs() if h["id"] != clean["id"]] + [clean])
            return self.store.host(clean["id"])

    def remove_host(self, host_id):
        with self.lock:
            self.refresh_settings()
            self.store.host(host_id)
            self.save_hosts([h for h in self.store.host_configs() if h["id"] != host_id])
        return {"removed": host_id}

    def start(self, ctx=None):
        with self.lock:
            if ctx is not None:
                self.context = ctx
            if self.thread and self.thread.is_alive():
                return
            self.stop_event.clear()
            self.thread = spawn_thread(self.loop, "paseo-executive-supervisor")

    def stop(self):
        self.stop_event.set()
        with self.lock:
            for proc in list(self.processes.values()):
                if proc.poll() is None:
                    proc.terminate()
        if self.thread:
            self.thread.join(timeout=2)

    def loop(self):
        while not self.stop_event.is_set():
            try:
                self.refresh_settings()
                if self.store.setting("monitor_enabled", True):
                    for host in self.store.hosts():
                        if host["enabled"] and (host["id"] not in self.workers or not self.workers[host["id"]].is_alive()):
                            self.workers[host["id"]] = spawn_thread(
                                lambda h=host: self.watch_host(h), f"paseo-host-{host['id']}")
                self.deliver()
            except Exception:
                log.exception("Executive supervisor iteration failed")
            self.stop_event.wait(2)

    def active(self, host):
        if self.stop_event.is_set() or not self.store.setting("monitor_enabled", True):
            return False
        try:
            current = self.store.host(host["id"])
            return current["enabled"] and all(current.get(k) == host.get(k) for k in
                                              ("home", "target", "stream_url", "password_env"))
        except ExecutiveError:
            return False

    def stream_config(self, host):
        url = host.get("stream_url")
        if not url and host.get("home"):
            status = self.executive.cli.call(host, "status")
            listen = status.get("listen", "")
            if not listen or listen.startswith("/"):
                return None
            url = "ws://" + listen + "/ws"
        if not url:
            return None
        password = None
        if host.get("password_env"):
            from agent.secret_scope import get_secret
            password = get_secret(host["password_env"])
        return dict(url=url, home=host.get("home"), password=password)

    def watch_host(self, host):
        host_id = host["id"]
        delay = 2
        try:
            while self.active(host):
                if not self.store.lease("host:" + host_id, self.owner, 120):
                    self.stop_event.wait(5)
                    continue
                try:
                    # Reconcile durable baselines before establishing/re-establishing a stream.
                    self.executive.poll(host_id)
                    self.store.health(host_id, connected=True, transport="poll")
                    config = self.stream_config(host)
                    bridge = Path(__file__).resolve().parent.parent / "bridge" / "watch.mjs"
                    node = shutil.which("node")
                    installed = (bridge.parent / "node_modules" / "@getpaseo" / "client").exists()
                    if config and node and installed:
                        self.stream(host, node, bridge, config)
                    else:
                        # The CLI owns SSH/pairing and local-socket auth. Polling is the
                        # fallback where a direct SDK WebSocket endpoint isn't configured.
                        deadline = time.monotonic() + 10
                        while self.active(host) and time.monotonic() < deadline:
                            self.stop_event.wait(1)
                    delay = 2
                except Exception as exc:
                    self.store.health(host_id, connected=False, error=str(exc)[:1500], retry_seconds=delay)
                    self.stop_event.wait(delay)
                    delay = min(delay * 2, 60)
        finally:
            self.store.release("host:" + host_id, self.owner)

    def stream(self, host, node, bridge, config):
        import queue
        proc = subprocess.Popen([node, str(bridge)], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                env=os.environ.copy())
        with self.lock:
            self.processes[host["id"]] = proc
        messages = queue.Queue(maxsize=1000)

        def read():
            for line in proc.stdout:
                while proc.poll() is None and not self.stop_event.is_set():
                    try:
                        messages.put(line, timeout=1)
                        break
                    except queue.Full:
                        continue
            try:
                messages.put_nowait(None)
            except queue.Full:
                pass

        reader = spawn_thread(read, f"paseo-stream-{host['id']}")
        try:
            proc.stdin.write(json.dumps(config) + "\n")
            proc.stdin.close()
            heartbeat_deadline = time.monotonic() + 25
            renew = time.monotonic()
            reconciled = time.monotonic()
            while self.active(host):
                if time.monotonic() - reconciled > 60:
                    self.executive.poll(host["id"])
                    reconciled = time.monotonic()
                if time.monotonic() - renew > 20:
                    if not self.store.lease("host:" + host["id"], self.owner, 120):
                        break
                    renew = time.monotonic()
                try:
                    line = messages.get(timeout=1)
                except queue.Empty:
                    if proc.poll() is not None:
                        raise ExecutiveError("Paseo SDK subscription exited; reconnecting")
                    if time.monotonic() > heartbeat_deadline:
                        raise ExecutiveError("Paseo SDK subscription heartbeat lost; reconciling")
                    continue
                if line is None:
                    raise ExecutiveError("Paseo SDK stream closed; reconnecting")
                frame = json.loads(line)
                heartbeat_deadline = time.monotonic() + 40
                if frame.get("type") == "snapshot":
                    self.store.observe(host["id"], frame["agent"], expected_host=host)
                elif frame.get("type") == "error":
                    raise ExecutiveError(frame["message"])
                elif frame.get("type") == "ready":
                    self.store.health(host["id"], connected=True, transport="sdk-subscription")
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
            proc.stdout.close()
            reader.join(timeout=2)
            with self.lock:
                self.processes.pop(host["id"], None)

    def deliver(self):
        route = self.store.setting("notification_session_key") or (self.context.get_config("notification_session_key") if self.context else None)
        for event in self.store.events(limit=50, unread=True, notifications_only=True):
            if event["kind"] not in {"completed", "failed", "permission"} or not self.store.claim_event(event["id"]):
                continue
            try:
                from hermes_cli.plugin_events import broadcast_plugin_event
                broadcast_plugin_event(PLUGIN_ID, "worker.event", event)
                if self.context:
                    self.context.emit("worker.event", event)
                success = bool(self.context and self.context.inject_message(event_message(event), session_key=route))
            except Exception:
                log.exception("Cannot deliver Paseo event %s; retaining it in the outbox", event["id"])
                success = False
            self.store.delivered(event["id"], success)


def profile_key():
    from hermes_constants import get_hermes_home
    return str(get_hermes_home().resolve())


def bind_context(ctx):
    key = profile_key()
    with _guard:
        _contexts[key] = ctx

    def unbind():
        with _guard:
            if _contexts.get(key) is ctx:
                _contexts.pop(key, None)
            owned = [runtime for runtime in _instances.values() if runtime.context is ctx]
        # API-created monitors have the same lifecycle owner as tool-created ones.
        for runtime in owned:
            runtime.stop()
            runtime.context = None
    return unbind


def get_runtime(ctx=None):
    from plugins.plugin_storage import plugin_data_dir
    directory = plugin_data_dir(PLUGIN_ID)
    with _guard:
        ctx = ctx or _contexts.get(profile_key())
        runtime = _instances.get(str(directory))
        if runtime is None:
            runtime = _instances[str(directory)] = Runtime(Store(directory), PaseoCLI(ctx.get_config("cli_path") if ctx else None))
        if ctx:
            runtime.context = ctx
            runtime.executive.cli = PaseoCLI(ctx.get_config("cli_path"))
        runtime.refresh_settings()
        return runtime
