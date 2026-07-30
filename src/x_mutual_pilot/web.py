"""Loopback-only approval dashboard using the Python standard library."""

from __future__ import annotations

from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import secrets
from typing import Mapping
from urllib.parse import parse_qs

from .store import Store, StoreConflict, StoreError


class DashboardApp:
    def __init__(
        self, store: Store, account_id: int, *, csrf_token: str | None = None
    ) -> None:
        self.store = store
        self.account_id = account_id
        self.csrf_token = csrf_token or secrets.token_urlsafe(32)

    def render_dashboard(self, *, notice: str = "") -> str:
        account = self.store.get_account(self.account_id)
        counts = self.store.dashboard_counts(self.account_id)
        alerts = self.store.active_alerts(self.account_id)
        candidates = self.store.list_candidates(self.account_id, limit=50)
        cards = "".join(self._render_candidate(item) for item in candidates)
        if not cards:
            cards = '<div class="empty">No candidates waiting for review.</div>'
        pause_label = "Writes paused" if account["writes_paused"] else "Writes enabled"
        pause_class = "safe" if account["writes_paused"] else "warning"
        notice_html = f'<div class="notice">{escape(notice)}</div>' if notice else ""
        alert_html = "".join(
            f'<div class="notice">{escape(alert["message"])}</div>'
            for alert in alerts
            if alert["code"] != "writes_paused"
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>X Mutual Pilot</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b0d10; --panel: #141820; --line: #29303c;
      --text: #f4f6f8; --muted: #9ba7b6; --accent: #73e2a7;
      --warn: #ffca68; --danger: #ff7b7b;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text);
      font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, sans-serif; }}
    main {{ max-width: 1160px; margin: 0 auto; padding: 40px 24px 80px; }}
    header {{ display: flex; justify-content: space-between; gap: 24px;
      align-items: flex-start; margin-bottom: 32px; }}
    h1 {{ margin: 0; font-size: clamp(30px, 5vw, 56px); line-height: 1; }}
    .eyebrow {{ color: var(--accent); text-transform: uppercase;
      letter-spacing: .14em; font-size: 12px; margin-bottom: 12px; }}
    .mode {{ color: var(--muted); margin-top: 12px; }}
    .pill {{ border: 1px solid var(--line); border-radius: 999px;
      padding: 10px 14px; white-space: nowrap; }}
    .safe {{ color: var(--accent); }} .warning {{ color: var(--warn); }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 1px; background: var(--line); border: 1px solid var(--line);
      margin-bottom: 32px; }}
    .metric {{ background: var(--panel); padding: 20px; }}
    .metric b {{ display: block; font-size: 28px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    .toolbar {{ display: flex; gap: 10px; justify-content: space-between;
      align-items: center; margin: 24px 0 14px; }}
    h2 {{ margin: 0; font-size: 22px; }}
    .queue {{ display: grid; gap: 12px; }}
    article {{ border: 1px solid var(--line); background: var(--panel);
      padding: 20px; }}
    .row {{ display: flex; justify-content: space-between; gap: 16px; }}
    .kind {{ text-transform: uppercase; letter-spacing: .12em;
      color: var(--accent); font-size: 11px; }}
    .status {{ color: var(--muted); }}
    .draft {{ width: 100%; min-height: 82px; margin: 14px 0;
      padding: 12px; resize: vertical; border: 1px solid var(--line);
      background: #0d1117; color: var(--text); font: inherit; }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }}
    button {{ border: 1px solid var(--line); background: transparent;
      color: var(--text); padding: 9px 13px; cursor: pointer; }}
    button.primary {{ background: var(--accent); border-color: var(--accent);
      color: #07110b; font-weight: 700; }}
    button.danger {{ color: var(--danger); }}
    button.muted {{ color: var(--muted); }}
    .notice {{ border-left: 3px solid var(--accent); background: var(--panel);
      padding: 12px 16px; margin-bottom: 20px; }}
    .empty {{ color: var(--muted); border: 1px dashed var(--line); padding: 28px; }}
    @media (max-width: 720px) {{
      header {{ display: block; }} .pill {{ display: inline-block; margin-top: 18px; }}
      .metrics {{ grid-template-columns: repeat(2, 1fr); }}
      .row {{ display: block; }}
    }}
  </style>
</head>
<body>
<main>
  <header>
    <div><div class="eyebrow">Approval console</div><h1>X Mutual Pilot</h1>
      <div class="mode">Mode: {escape(str(account["mode"]))} · Account {escape(str(account["x_user_id"]))}</div>
    </div>
    <div class="pill {pause_class}">{pause_label}</div>
  </header>
  {notice_html}{alert_html}
  <section class="metrics">
    {self._metric("Pending", counts["pending"])}
    {self._metric("Approved", counts["approved"])}
    {self._metric("Mutuals", counts["mutuals"])}
    {self._metric("Executed", counts["executed"])}
  </section>
  <div class="toolbar">
    <h2>Review queue</h2>
    {self._pause_form(bool(account["writes_paused"]))}
  </div>
  <section class="queue">{cards}</section>
</main>
</body>
</html>"""

    @staticmethod
    def _metric(label: str, value: int) -> str:
        return f'<div class="metric"><b>{value}</b><span>{escape(label)}</span></div>'

    def _pause_form(self, paused: bool) -> str:
        if paused:
            return '<span class="meta">Resume from CLI with --confirm-resume</span>'
        return (
            '<form method="post" action="/pause">'
            f'<input type="hidden" name="csrf" value="{escape(self.csrf_token)}">'
            '<input type="hidden" name="actor" value="dashboard">'
            '<button class="danger">Pause writes</button></form>'
        )

    def _render_candidate(self, item: Mapping[str, object]) -> str:
        candidate_id = escape(str(item["id"]))
        draft = escape(str(item.get("draft") or ""))
        risks = ", ".join(str(value) for value in item["risk_flags"]) or "none"
        reasons = ", ".join(str(value) for value in item["reasons"]) or "none"
        controls = ""
        if item["status"] == "pending":
            controls = f"""
<div class="actions">
  <button class="primary" type="submit" formaction="/candidates/{candidate_id}/approve">Approve</button>
  <button class="muted" type="submit" formaction="/candidates/{candidate_id}/snooze">Snooze</button>
  <button class="danger" type="submit" formaction="/candidates/{candidate_id}/reject">Reject</button>
</div>"""
        return f"""<article>
  <form method="post">
    <input type="hidden" name="csrf" value="{escape(self.csrf_token)}">
    <input type="hidden" name="actor" value="dashboard">
    <div class="row"><div class="kind">{escape(str(item["action_type"]))}</div>
      <div class="status">{escape(str(item["status"]))} · score {int(item["score"])}</div></div>
    <div class="meta">User {escape(str(item["target_user_id"]))} · Post {escape(str(item.get("target_post_id") or "—"))}</div>
    <textarea class="draft" name="draft" aria-label="Reply draft">{draft}</textarea>
    <div class="meta">Reasons: {escape(reasons)} · Risks: {escape(risks)}</div>
    {controls}
  </form>
</article>"""

    def handle_action(
        self, path: str, fields: Mapping[str, list[str]]
    ) -> str:
        if fields.get("csrf", [""])[0] != self.csrf_token:
            raise ValueError("CSRF validation failed")
        actor = fields.get("actor", ["dashboard"])[0][:80]
        if path == "/pause":
            self.store.set_writes_paused(self.account_id, True, actor=actor)
            return "Writes paused."
        match = re.fullmatch(
            r"/candidates/([a-f0-9]+)/(?P<action>approve|reject|snooze)", path
        )
        if not match:
            raise ValueError("unknown action")
        candidate_id = match.group(1)
        if match.group("action") == "approve":
            edited = fields.get("draft", [None])[0]
            self.store.approve_candidate(
                candidate_id, actor=actor, edited_draft=edited
            )
            return "Candidate approved."
        if match.group("action") == "snooze":
            self.store.snooze_candidate(
                candidate_id, actor=actor, minutes=60
            )
            return "Candidate snoozed for one hour."
        self.store.reject_candidate(
            candidate_id, actor=actor, reason="Rejected in dashboard"
        )
        return "Candidate rejected."


def serve_dashboard(
    store: Store, account_id: int, *, host: str = "127.0.0.1", port: int = 8765
) -> None:
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("dashboard may only bind to loopback")
    app = DashboardApp(store, account_id)
    notices: dict[str, str] = {"last": ""}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if self.path != "/":
                self.send_error(404)
                return
            body = app.render_dashboard(notice=notices.pop("last", "")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            length = min(int(self.headers.get("Content-Length", "0")), 65536)
            fields = parse_qs(self.rfile.read(length).decode())
            try:
                notices["last"] = app.handle_action(self.path, fields)
            except (ValueError, StoreConflict, StoreError) as error:
                self.send_error(400, str(error))
                return
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
