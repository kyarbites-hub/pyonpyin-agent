"""Minimal authenticated admin UI and public read-only story catalogue."""

import hmac
import json
import os
import re
import secrets
import urllib.error
import urllib.request
import uuid
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, redirect, render_template_string, request, send_from_directory, session, url_for

from pyonpyin.core import (
    eligible_candidate,
    normalize_url,
    publication_blockers,
    safe_story_theme,
    utc_now,
)
from pyonpyin.sheets import SHEET_CELL_SAFE_LIMIT, SheetsStore


app = Flask(__name__)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
app.secret_key = os.environ.get("PYONPYIN_SESSION_SECRET") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("PYONPYIN_HTTPS", "").lower() == "true",
    PERMANENT_SESSION_LIFETIME=8 * 60 * 60,
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)


@app.after_request
def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "media-src 'self' https: blob:; img-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    if os.environ.get("PYONPYIN_HTTPS", "").lower() == "true":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response
PUBLIC_HTML = """<!doctype html><html lang="my"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PyonPyin Stories</title><style>
:root{font-family:'Myanmar Text','Noto Sans Myanmar',sans-serif;color:#182f38;background:#fff9ed}
body{margin:0}header{padding:3rem 7vw;background:linear-gradient(125deg,#163e48,#286e70);color:white}
h1{font-size:clamp(2rem,5vw,4rem);margin:.2em 0}nav{display:flex;gap:1rem;flex-wrap:wrap}
a{color:inherit}main{padding:2rem 7vw}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1.2rem}
article{background:white;border-radius:1.2rem;padding:1.4rem;box-shadow:0 8px 25px #243c3018}
.tag{color:#23745d;font-weight:700}audio{width:100%}.muted{color:#5a6a6d}
.cover{height:115px;border-radius:.9rem;margin-bottom:1rem;display:grid;place-items:center;font-size:2.2rem;color:#fff;
background:radial-gradient(circle at 78% 28%,#fff4b8 0 10%,transparent 11%),radial-gradient(circle at 20% 95%,#65a879 0 20%,transparent 21%),linear-gradient(135deg,#ef9c67,#725899);animation:glow 5s ease-in-out infinite alternate}
article:nth-of-type(3n+2) .cover{background:radial-gradient(circle at 74% 23%,#fff1b5 0 11%,transparent 12%),linear-gradient(155deg,#66bcc2 0 48%,#315d76 49% 72%,#163e48 73%)}
article:nth-of-type(3n) .cover{background:radial-gradient(circle at 70% 25%,#fff3c7 0 10%,transparent 11%),linear-gradient(145deg,#9471af,#d9876c 54%,#638f77)}
@keyframes glow{to{filter:hue-rotate(12deg);transform:translateY(-2px)}}details{padding:.4rem 0}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;scroll-behavior:auto!important}}
</style><header><div>ပုံပြင်ကမ္ဘာ · PYONPYIN</div><h1>ပုံပြင်များ၊ စိတ်ကူးကမ္ဘာများ</h1>
<nav><a href="#children">ကလေးများ</a><a href="#adult">လူကြီးများ</a></nav></header>
<main><p class="muted">အတည်ပြုပြီး ထုတ်ဝေထားသော ပုံပြင်များသာ ပြသထားပါသည်။</p>
{% for category, label in [('CHILDREN','ကလေးများအတွက်'),('ADULT','လူကြီးများအတွက်')] %}
<section id="{{ 'children' if category == 'CHILDREN' else 'adult' }}"><h2>{{ label }}</h2>
<div class="grid">{% for story in stories if story.category == category %}
<article><div class="cover" aria-hidden="true">✦　☾　✿</div><span class="tag">{{ label }}</span><h3>{{ story.myanmar_title }}</h3>
<p>{{ story.description }}</p><a href="{{ url_for('public_story', story_id=story.story_id) }}">ပုံပြင်ဖတ်ရန် →</a>
{% if story.audio_url and story.audio_status == 'READY' %}<audio controls preload="none" src="{{ story.audio_url }}"></audio>{% endif %}
{% for ep in story.episodes %}<details><summary>{{ ep.title }}</summary><p>{{ ep.content }}</p>
{% if ep.audio_url and ep.audio_status == 'READY' %}<audio controls preload="none" src="{{ ep.audio_url }}"></audio>{% endif %}</details>{% endfor %}
</article>{% endfor %}</div></section>{% endfor %}
<form><input name="q" placeholder="ပုံပြင်ရှာရန်" value="{{ query }}"></form></main></html>"""
ADMIN_HTML = """<!doctype html><html lang="my"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>PyonPyin Admin</title><style>body{font:16px 'Myanmar Text','Noto Sans Myanmar',sans-serif;background:#eff5f1;color:#18343a;margin:0}
header{background:#164951;color:white;padding:1.5rem 6vw}main{padding:2rem 6vw}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}
article{background:white;border-radius:1rem;padding:1.2rem;box-shadow:0 6px 20px #19342c15}input,textarea,select,button{font:inherit;padding:.6rem;margin:.25rem;max-width:100%}
textarea{width:96%;min-height:180px}button{border:0;border-radius:.5rem;background:#19735d;color:white;cursor:pointer}.bad{color:#a33}.status{font-weight:bold}
</style><header><h1>PyonPyin · စီမံခန့်ခွဲမှု</h1><form method="post" action="/admin/logout"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"><button>ထွက်ရန်</button></form></header><main>
<p>မူကြမ်းများသည် အများမြင်စာမျက်နှာတွင် မပေါ်ပါ။ Rights၊ review၊ episodes နှင့် approval အားလုံးဖြည့်ပြီးမှသာ publish လုပ်နိုင်သည်။</p>
<div class="grid">{% for story in stories %}<article><span>{{ story.category }}</span><h2>{{ story.original_title }}</h2>
<p><a href="{{ story.source_url }}">{{ story.source_name }} · မူရင်းရင်းမြစ်</a></p>
<p>License: {{ story.license_status or 'REVIEW_REQUIRED' }} · {{ story.review_status }} ·
{{ story.rights_jurisdiction or 'JURISDICTION_REVIEW_REQUIRED' }}
{% if story.license_name %} · {{ story.license_name }}{% endif %}
{% if story.license_url %} · License URL: {{ story.license_url }}{% endif %}
{% if story.license_evidence %} · Evidence: {{ story.license_evidence }}{% endif %}
{% if story.category_evidence %} · Category: {{ story.category_evidence }}{% endif %}</p>
<form method="post" action="/admin/story/{{ story.story_id }}">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>အမျိုးအစား <select name="category"><option value="UNCLASSIFIED" {% if story.category == 'UNCLASSIFIED' %}selected{% endif %}>UNCLASSIFIED</option><option value="CHILDREN" {% if story.category == 'CHILDREN' %}selected{% endif %}>CHILDREN</option><option value="ADULT" {% if story.category == 'ADULT' %}selected{% endif %}>ADULT</option></select></label>
<label>License evidence <input name="license_evidence" value="{{ story.license_evidence }}"></label>
<label>Rights jurisdiction <input name="rights_jurisdiction" value="{{ story.rights_jurisdiction }}"></label>
<label>Reviewer <input name="human_reviewer" value="{{ story.human_reviewer }}"></label>
<label>Rights cleared <select name="rights_cleared"><option {% if story.rights_cleared != 'YES' %}selected{% endif %}>NO</option><option {% if story.rights_cleared == 'YES' %}selected{% endif %}>YES</option></select></label>
<label>License status <select name="license_status"><option {% if story.license_status != 'APPROVED' %}selected{% endif %}>NEEDS_LICENSE_REVIEW</option><option {% if story.license_status == 'APPROVED' %}selected{% endif %}>APPROVED</option><option {% if story.license_status == 'REJECTED' %}selected{% endif %}>REJECTED</option></select></label>
<label>Translation rights <select name="permission_for_translation"><option {% if story.permission_for_translation != 'YES' %}selected{% endif %}>NO</option><option {% if story.permission_for_translation == 'YES' %}selected{% endif %}>YES</option></select></label>
<label>AI processing rights <select name="permission_for_ai_processing"><option {% if story.permission_for_ai_processing != 'YES' %}selected{% endif %}>NO</option><option {% if story.permission_for_ai_processing == 'YES' %}selected{% endif %}>YES</option></select></label>
<label>Public distribution rights <select name="permission_for_publication"><option {% if story.permission_for_publication != 'YES' %}selected{% endif %}>NO</option><option {% if story.permission_for_publication == 'YES' %}selected{% endif %}>YES</option></select></label>
<label>Audio rights <select name="permission_for_audio"><option {% if story.permission_for_audio != 'YES' %}selected{% endif %}>NO</option><option {% if story.permission_for_audio == 'YES' %}selected{% endif %}>YES</option></select></label>
<label>Commercial reuse rights (future) <select name="permission_for_commercial_use"><option {% if story.permission_for_commercial_use != 'YES' %}selected{% endif %}>NO</option><option {% if story.permission_for_commercial_use == 'YES' %}selected{% endif %}>YES</option></select></label>
<button>Save review</button></form>
<form method="post" action="/admin/story/{{ story.story_id }}/queue">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Rights-cleared source text for production <textarea name="source_text">{{ story.source_text }}</textarea></label>
<button>Save selection and queue draft</button></form>
<details><summary>Production / episode preview</summary><p>{{ story.myanmar_title }}</p>
<pre>{{ story.myanmar_story }}</pre>{% for ep in story.episodes %}<h3 id="{{ story.story_id }}-episode-{{ ep.episode_number }}">{{ ep.episode_number }}. {{ ep.title }}</h3><nav>
{% if not loop.first %}<a href="#{{ story.story_id }}-episode-{{ ep.episode_number|int - 1 }}">← Previous</a>{% endif %}
{% if not loop.last %}<a href="#{{ story.story_id }}-episode-{{ ep.episode_number|int + 1 }}">Next →</a>{% endif %}</nav>
<pre>{{ ep.content }}</pre>{% if ep.audio_url and ep.audio_status == 'READY' %}<audio controls preload="none" src="{{ ep.audio_url }}"></audio>{% endif %}{% endfor %}
{% if story.audio_url and story.audio_status == 'READY' %}<audio controls src="{{ story.audio_url }}"></audio>{% endif %}
<p>Status: {{ story.processing_status }} · Draft mode: {{ story.draft_mode or 'NOT_QUEUED' }} {{ story.processing_error }}</p></details>
<form method="post" action="/admin/story/{{ story.story_id }}/edit-production">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Myanmar title <input name="myanmar_title" value="{{ story.myanmar_title }}"></label>
<label>Myanmar story <textarea name="myanmar_story">{{ story.myanmar_story }}</textarea></label>
<label>Episodes JSON <textarea name="episodes_json">{{ story.episodes_json }}</textarea></label>
<label>Quiz JSON <textarea name="quiz_json">{{ story.quiz_json }}</textarea></label>
<label>Reflection JSON <textarea name="reflection_json">{{ story.reflection_json }}</textarea></label>
<label>Audio file URL <input name="audio_url" value="{{ story.audio_url }}"></label>
<label>Audio status <select name="audio_status"><option>{{ story.audio_status or 'NOT_READY' }}</option><option>READY</option><option>NOT_READY</option></select></label>
<label>Audio required for publication <select name="audio_required"><option value="YES" {% if story.audio_required != 'NO' %}selected{% endif %}>YES</option><option value="NO" {% if story.audio_required == 'NO' %}selected{% endif %}>NO</option></select></label>
<button>Save Myanmar draft</button></form>
<form method="post" action="/admin/story/{{ story.story_id }}/publish">
<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
<label>Content review <select name="content_review_status"><option>PENDING</option><option>APPROVED</option></select></label>
<label>Approve publication <input type="checkbox" name="approval_status" value="APPROVED" required></label>
<label>Your name <input name="approved_by" required></label><button>Approve & publish</button></form>
{% if story.blockers %}<p class="bad">{{ story.blockers|join(' ') }}</p>{% endif %}
</article>{% endfor %}</div><h2>Publishing History</h2><pre>{{ history }}</pre></main></html>"""


def _store(initialize=False):
    store = SheetsStore()
    if initialize:
        store.ensure_schema()
    return store


def _episode_json(store, story_id, production, segmented=None, episode_rows=None):
    inline = production.get("episodes_json", "")
    if inline:
        return inline
    if segmented is None:
        segmented = store.read_texts("EPISODES")
    if story_id in segmented:
        return segmented[story_id]
    if episode_rows is None:
        episode_rows = store.read_records("Story Episodes")
    rows = [
        row for row in episode_rows
        if row.get("story_id") == story_id and row.get("complete", "").upper() == "YES"
    ]
    rows.sort(key=lambda row: int(row.get("episode_number", 0)))
    for row in rows:
        row["episode_number"] = int(row.get("episode_number", 0))
    return json.dumps(rows, ensure_ascii=False)


@app.context_processor
def inject_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return {"csrf_token": lambda: session["csrf_token"]}


@app.before_request
def check_admin_csrf():
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and (
        request.path.startswith("/admin/")
        or request.path.startswith("/api/admin/")
    ) and request.path not in {"/admin/login", "/api/admin/login"}:
        expected = session.get("csrf_token", "")
        provided = (
            request.headers.get("X-CSRF-Token", "")
            or request.form.get("csrf_token", "")
        )
        if not expected or not hmac.compare_digest(expected, provided):
            abort(400, "Invalid or missing CSRF token.")


def _admin_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login"))
        return function(*args, **kwargs)
    return wrapped


def _admin_api_required(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return jsonify({"error": "Authentication required."}), 401
        return function(*args, **kwargs)
    return wrapped


def _frontend_file(path="index.html"):
    if not FRONTEND_DIST.is_dir():
        abort(404, "Frontend assets are not built. Run npm run build in frontend/.")
    return send_from_directory(FRONTEND_DIST, path)


@app.get("/app")
def frontend_app():
    return _frontend_file()


@app.get("/app/<path:asset>")
def frontend_asset(asset):
    return _frontend_file(asset)


@app.get("/assets/<path:asset>")
def frontend_built_asset(asset):
    return _frontend_file(f"assets/{asset}")


@app.get("/admin/app")
def frontend_admin_app():
    return _frontend_file()


@app.get("/admin/app/<path:asset>")
def frontend_admin_asset(asset):
    return _frontend_file(asset)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    password = os.environ.get("PYONPYIN_ADMIN_PASSWORD")
    session_secret = os.environ.get("PYONPYIN_SESSION_SECRET")
    if not password or not session_secret:
        abort(503, "Set PYONPYIN_ADMIN_PASSWORD and PYONPYIN_SESSION_SECRET to enable dashboard access.")
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("password", ""), password):
            session["admin_authenticated"] = True
            session.permanent = True
            return redirect(url_for("admin"))
        abort(401)
    return """<!doctype html><meta charset=utf-8><title>Admin login</title>
    <form method=post><label>Admin password <input type=password name=password required></label>
    <button>Sign in</button></form>"""


@app.post("/api/admin/login")
def admin_api_login():
    password = os.environ.get("PYONPYIN_ADMIN_PASSWORD")
    session_secret = os.environ.get("PYONPYIN_SESSION_SECRET")
    if not password or not session_secret:
        return jsonify({
            "error": "Admin authentication is not configured on this server."
        }), 503
    supplied = request.get_json(silent=True) or {}
    if not isinstance(supplied, dict) or not hmac.compare_digest(
        str(supplied.get("password", "")), password
    ):
        return jsonify({"error": "Invalid credentials."}), 401
    session.clear()
    session["admin_authenticated"] = True
    session.permanent = True
    session["csrf_token"] = secrets.token_urlsafe(32)
    return jsonify({"csrf_token": session["csrf_token"]})


@app.post("/api/admin/logout")
@_admin_api_required
def admin_api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/admin/overview")
@_admin_api_required
def admin_api_overview():
    store = _store()
    csrf_token = session.get("csrf_token")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        session["csrf_token"] = csrf_token
    library = store.read_records("Story Library")
    production = store.read_records("Story Production")
    published_ids = {
        row.get("story_id")
        for row in store.read_records("Publishing History")
        if row.get("publication_status", "").strip().upper() == "PUBLISHED"
    }
    production_by_id = {row.get("story_id"): row for row in production}
    pending_review = sum(
        1 for story in library
        if story.get("review_status", "").strip().upper() != "REVIEWED"
        or story.get("license_status", "").strip().upper() == "NEEDS_LICENSE_REVIEW"
    )
    rights_review = sum(
        1 for story in library
        if story.get("rights_cleared", "").strip().upper() != "YES"
        or story.get("license_status", "").strip().upper()
        in {"", "NEEDS_LICENSE_REVIEW", "PENDING_REVIEW"}
    )
    content_review = sum(
        1 for row in production
        if row.get("processing_status", "").strip().upper() in {
            "DRAFT_READY", "HUMAN_EDITING"
        }
        and row.get("content_review_status", "").strip().upper() != "APPROVED"
    )
    approved = sum(
        1 for story in library
        if eligible_candidate(story)
        and production_by_id.get(story.get("story_id"), {}).get(
            "content_review_status", ""
        ).strip().upper() == "APPROVED"
        and production_by_id.get(story.get("story_id"), {}).get(
            "approval_status", ""
        ).strip().upper() == "APPROVED"
    )
    drafts = sum(
        1 for row in production
        if row.get("processing_status", "").strip().upper()
        in {"DRAFT_READY", "HUMAN_EDITING"}
    )
    audio_ready = sum(
        1 for row in production
        if row.get("audio_status", "").strip().upper() == "READY"
    )
    return jsonify({
        "csrf_token": csrf_token,
        "counts": {
            "stories": len(library),
            "pending_review": pending_review,
            "rights_review": rights_review,
            "content_review": content_review,
            "approved": approved,
            "drafts": drafts,
            "audio_ready": audio_ready,
            "published": len(published_ids),
        },
        "stories": [
            {
                "story_id": story.get("story_id", ""),
                "title": story.get("original_title", ""),
                "category": story.get("category", "UNCLASSIFIED"),
                "license_status": story.get("license_status", ""),
                "license_name": story.get("license_name", ""),
                "review_status": story.get("review_status", ""),
                "processing_status": production_by_id.get(
                    story.get("story_id"), {}
                ).get("processing_status", "NOT_QUEUED"),
                "processing_error": production_by_id.get(
                    story.get("story_id"), {}
                ).get("processing_error", ""),
                "audio_status": production_by_id.get(
                    story.get("story_id"), {}
                ).get("audio_status", ""),
                "source_name": story.get("source_name", ""),
                "source_url": normalize_url(story.get("source_url", "")),
                "license_evidence": story.get("license_evidence", ""),
                "license_url": story.get("license_url", ""),
                "rights_jurisdiction": story.get("rights_jurisdiction", ""),
                "rights_cleared": story.get("rights_cleared", "NO"),
                "permission_for_translation": story.get("permission_for_translation", "NO"),
                "permission_for_ai_processing": story.get("permission_for_ai_processing", "NO"),
                "permission_for_publication": story.get("permission_for_publication", "NO"),
                "permission_for_audio": story.get("permission_for_audio", "NO"),
                "permission_for_commercial_use": story.get("permission_for_commercial_use", "NO"),
                "human_reviewer": story.get("human_reviewer", ""),
                "category_evidence": story.get("category_evidence", ""),
                "published": story.get("story_id") in published_ids,
            }
            for story in library
        ],
    })


@app.get("/api/admin/jobs")
@_admin_api_required
def admin_api_jobs():
    store = _store()
    history = store.read_records("Processing History")
    publications = store.read_records("Publishing History")
    active = [
        row for row in store.read_records("Story Production")
        if row.get("processing_status", "").strip().upper()
        in {"QUEUED", "DISPATCHED", "GENERATING"}
    ]
    recent = sorted(
        history,
        key=lambda row: row.get("started_at", ""),
        reverse=True,
    )[:50]
    return jsonify({
        "active": [
            {
                "story_id": row.get("story_id", ""),
                "status": row.get("processing_status", ""),
                "error": row.get("processing_error", ""),
                "updated_at": row.get("updated_at", ""),
            }
            for row in active
        ],
        "history": [
            {
                "processing_id": row.get("processing_id", ""),
                "story_id": row.get("story_id", ""),
                "status": row.get("status", ""),
                "started_at": row.get("started_at", ""),
                "completed_at": row.get("completed_at", ""),
                "retry_count": row.get("retry_count", "0"),
                "error_details": row.get("error_details", ""),
            }
            for row in recent
        ],
        "publishing_history": [
            {
                "story_id": row.get("story_id", ""),
                "published_title": row.get("published_title", ""),
                "website_url": row.get("website_url", ""),
                "published_at": row.get("published_at", ""),
                "publication_status": row.get("publication_status", ""),
                "approved_by": row.get("approved_by", ""),
            }
            for row in sorted(
                publications,
                key=lambda item: item.get("published_at", ""),
                reverse=True,
            )[:50]
        ],
        "dispatch_configured": _github_dispatch_settings() is not None,
    })


def _github_dispatch_settings():
    token = os.environ.get("PYONPYIN_GITHUB_TOKEN", "").strip()
    repository = os.environ.get("PYONPYIN_GITHUB_REPOSITORY", "").strip()
    ref = os.environ.get("PYONPYIN_GITHUB_REF", "main").strip()
    repository_parts = repository.split("/")
    if not (
        os.environ.get("PYONPYIN_GITHUB_DISPATCH_ENABLED", "").lower() == "true"
        and os.environ.get("PYONPYIN_GEMINI_AUTOMATION_ENABLED", "").lower() == "true"
        and token
        and len(repository_parts) == 2
        and all(
            re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", part) and part not in {".", ".."}
            for part in repository_parts
        )
        and re.fullmatch(r"[A-Za-z0-9._/-]{1,200}", ref)
        and all(part not in {"", ".", ".."} for part in ref.split("/"))
    ):
        return None
    return token, repository, ref


@app.post("/api/admin/jobs/dispatch")
@_admin_api_required
def admin_api_dispatch_job():
    settings = _github_dispatch_settings()
    if settings is None:
        abort(503, "GitHub dispatch is disabled or missing server-side configuration.")
    token, repository, ref = settings
    body = request.get_json(silent=True)
    story_id = body.get("story_id") if isinstance(body, dict) else None
    if not isinstance(story_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", story_id):
        abort(400, "A valid queued story_id is required.")

    store = _store()
    library = next(
        (row for row in store.read_records("Story Library") if row.get("story_id") == story_id),
        None,
    )
    production = next(
        (row for row in store.read_records("Story Production") if row.get("story_id") == story_id),
        None,
    )
    if library is None or production is None:
        abort(404, "Queued story was not found.")
    if production.get("processing_status", "").strip().upper() != "QUEUED":
        abort(409, "Story is not queued or has already been dispatched.")
    if any(
        row.get("story_id") != story_id
        and row.get("processing_status", "").strip().upper() in {"DISPATCHED", "GENERATING"}
        for row in store.read_records("Story Production")
    ):
        abort(409, "Another story is already dispatched or generating; wait for it to finish.")
    draft_mode = production.get("draft_mode", "").strip().upper()
    if draft_mode == "ORIGINAL_THEME":
        if (
            library.get("category", "").strip().upper() not in {"CHILDREN", "ADULT"}
            or not library.get("category_evidence", "").strip()
            or not safe_story_theme(library.get("category", ""), library.get("broad_theme", ""))
        ):
            abort(409, "Theme-only generation requires a reviewed category and safe broad theme.")
    elif not eligible_candidate(library):
        abort(409, "Source-based generation requires explicit rights and permissions.")
    elif draft_mode not in {"PUBLIC_DOMAIN_RETELLING", "RIGHTS_CLEARED_SOURCE"}:
        abort(409, "Unsupported draft mode.")

    processing_id = f"{story_id}-dispatch-{uuid.uuid4().hex[:12]}"
    started_at = utc_now()
    production.update({
        "processing_status": "DISPATCHED",
        "processing_error": "",
    })
    store.write_production(production)
    store.record_processing({
        "processing_id": processing_id,
        "story_id": story_id,
        "status": "DISPATCHED",
        "started_at": started_at,
        "completed_at": "",
        "retry_count": "0",
        "error_details": "",
    })

    payload = json.dumps({
        "ref": ref,
        "inputs": {"story_id": story_id},
    }).encode("utf-8")
    dispatch = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/actions/workflows/process-stories.yml/dispatches",
        data=payload,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(dispatch, timeout=10) as response:
            if response.status != 204:
                raise RuntimeError("GitHub did not accept the workflow dispatch.")
    except urllib.error.HTTPError as exc:
        production.update({
            "processing_status": "DISPATCH_FAILED",
            "processing_error": f"GitHub Actions rejected dispatch (HTTP {exc.code}).",
        })
        store.write_production(production)
        store.record_processing({
            "processing_id": processing_id,
            "story_id": story_id,
            "status": "DISPATCH_FAILED",
            "started_at": started_at,
            "completed_at": utc_now(),
            "retry_count": "0",
            "error_details": f"GitHub Actions rejected dispatch (HTTP {exc.code}).",
        })
        abort(502, f"GitHub Actions rejected workflow dispatch (HTTP {exc.code}).")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        production.update({
            "processing_status": "DISPATCH_UNKNOWN",
            "processing_error": "Dispatch outcome is unknown; reconcile GitHub Actions before retrying.",
        })
        store.write_production(production)
        store.record_processing({
            "processing_id": processing_id,
            "story_id": story_id,
            "status": "DISPATCH_UNKNOWN",
            "started_at": started_at,
            "completed_at": utc_now(),
            "retry_count": "0",
            "error_details": type(exc).__name__,
        })
        abort(502, "GitHub Actions dispatch outcome is unknown; inspect Actions before any retry.")
    return jsonify({"ok": True, "story_id": story_id, "status": "DISPATCHED"}), 202


@app.get("/api/admin/story/<story_id>")
@_admin_api_required
def admin_api_story(story_id):
    store = _store()
    story = next(
        (row for row in store.read_records("Story Library") if row.get("story_id") == story_id),
        None,
    )
    if story is None:
        abort(404)
    production = next(
        (row for row in store.read_records("Story Production") if row.get("story_id") == story_id),
        {},
    )
    if not production.get("myanmar_story"):
        production["myanmar_story"] = store.read_texts("MYANMAR").get(story_id, "")
    production["episodes_json"] = _episode_json(store, story_id, production)
    try:
        episodes = json.loads(production.get("episodes_json") or "[]")
        quiz = json.loads(production.get("quiz_json") or "[]")
        reflection = json.loads(production.get("reflection_json") or "[]")
    except json.JSONDecodeError:
        abort(409, "The saved draft contains invalid JSON and requires administrator repair.")
    return jsonify({
        "story": {
            key: story.get(key, "")
            for key in (
                "story_id", "original_title", "author", "source_name",
                "source_url", "source_text", "category", "category_evidence",
                "license_status", "license_name", "license_url",
                "license_evidence", "rights_cleared", "rights_jurisdiction",
                "permission_for_translation", "permission_for_ai_processing",
                "permission_for_publication", "permission_for_audio",
                "human_reviewer", "review_status", "rights_mode",
            )
        },
        "production": {
            key: production.get(key, "")
            for key in (
                "myanmar_title", "myanmar_story", "audio_url", "audio_status",
                "audio_required", "processing_status", "processing_error",
                "content_review_status", "approval_status", "draft_mode",
            )
        },
        "episodes": episodes if isinstance(episodes, list) else [],
        "quiz": quiz if isinstance(quiz, list) else [],
        "reflection": reflection,
    })


@app.put("/api/admin/story/<story_id>/rights-review")
@_admin_api_required
def admin_api_rights_review(story_id):
    store = _store()
    story = next(
        (row for row in store.read_records("Story Library") if row.get("story_id") == story_id),
        None,
    )
    if story is None:
        abort(404, "Story Library record does not exist.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "A JSON rights-review object is required.")

    category = body.get("category")
    category_evidence = body.get("category_evidence")
    license_status = body.get("license_status")
    rights_cleared = body.get("rights_cleared")
    human_reviewer = body.get("human_reviewer")
    license_evidence = body.get("license_evidence")
    rights_jurisdiction = body.get("rights_jurisdiction")
    permission_fields = (
        "permission_for_translation",
        "permission_for_ai_processing",
        "permission_for_publication",
        "permission_for_audio",
        "permission_for_commercial_use",
    )

    if not isinstance(category, str) or category not in {
        "CHILDREN", "ADULT", "UNCLASSIFIED"
    }:
        abort(400, "Choose an explicit supported category.")
    if (
        not isinstance(category_evidence, str)
        or len(category_evidence) > 5_000
        or category in {"CHILDREN", "ADULT"} and not category_evidence.strip()
    ):
        abort(400, "Classified stories require category evidence of at most 5,000 characters.")
    if not isinstance(license_status, str) or license_status not in {
        "NEEDS_LICENSE_REVIEW", "PENDING_REVIEW", "APPROVED", "REJECTED"
    }:
        abort(400, "Unsupported license status.")
    if not isinstance(rights_cleared, str) or rights_cleared not in {"YES", "NO"}:
        abort(400, "Rights clearance must be YES or NO.")
    text_fields = {
        "human_reviewer": human_reviewer,
        "license_evidence": license_evidence,
        "rights_jurisdiction": rights_jurisdiction,
    }
    if any(
        not isinstance(value, str) or len(value) > 5_000
        for value in text_fields.values()
    ):
        abort(400, "Reviewer and rights evidence fields must be text under 5,000 characters.")
    if any(
        not isinstance(body.get(field), str) or body[field] not in {"YES", "NO"}
        for field in permission_fields
    ):
        abort(400, "Each rights permission must be explicitly YES or NO.")
    if rights_cleared == "YES" and not (
        license_status == "APPROVED"
        and human_reviewer.strip()
        and license_evidence.strip()
        and rights_jurisdiction.strip()
        and body["permission_for_translation"] == "YES"
        and body["permission_for_ai_processing"] == "YES"
    ):
        abort(
            409,
            "Rights clearance requires approved license evidence, reviewer, jurisdiction, "
            "and explicit translation and AI-processing permission.",
        )

    updated = {
        **story,
        "category": category,
        "category_evidence": category_evidence.strip(),
        "license_status": license_status,
        "rights_cleared": rights_cleared,
        "human_reviewer": human_reviewer.strip(),
        "license_evidence": license_evidence.strip(),
        "rights_jurisdiction": rights_jurisdiction.strip(),
        "review_status": "REVIEWED",
        **{field: body[field] for field in permission_fields},
    }
    store.upsert_story(updated)
    return jsonify({
        "ok": True,
        "category": updated["category"],
        "license_status": updated["license_status"],
        "rights_cleared": updated["rights_cleared"],
        "review_status": updated["review_status"],
    })


@app.put("/api/admin/story/<story_id>/draft")
@_admin_api_required
def admin_api_save_draft(story_id):
    store = _store()
    library_story = next(
        (
            row for row in store.read_records("Story Library")
            if row.get("story_id") == story_id
        ),
        None,
    )
    if not library_story:
        abort(404)
    production = next(
        (row for row in store.read_records("Story Production") if row.get("story_id") == story_id),
        None,
    )
    if production is None:
        abort(404, "Production draft does not exist.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, "A JSON draft object is required.")
    title = body.get("myanmar_title")
    story_text = body.get("myanmar_story")
    episodes = body.get("episodes")
    quiz = body.get("quiz")
    reflection = body.get("reflection")
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        abort(400, "Myanmar story title is required and must be at most 500 characters.")
    if (
        not isinstance(story_text, str)
        or not story_text.strip()
        or len(story_text) > 200_000
    ):
        abort(400, "Myanmar story text is required and must be at most 200,000 characters.")
    if not isinstance(episodes, list) or not episodes or len(episodes) > 100:
        abort(400, "Provide between 1 and 100 ordered episodes.")
    if any(
        not isinstance(episode, dict)
        or type(episode.get("episode_number")) is not int
        or episode["episode_number"] != index
        or not isinstance(episode.get("title"), str)
        or not episode["title"].strip()
        or not isinstance(episode.get("content"), str)
        or not episode["content"].strip()
        or len(episode["content"]) > SHEET_CELL_SAFE_LIMIT
        for index, episode in enumerate(episodes, 1)
    ):
        abort(400, "Episodes must be complete, ordered, titled, and within the safe cell size.")
    complete_text = " ".join(story_text.split())
    episode_text = " ".join("".join(item["content"] for item in episodes).split())
    if complete_text != episode_text:
        abort(400, "Episode contents must exactly preserve the complete story in order.")
    if (
        not isinstance(quiz, list)
        or not quiz
        or len(quiz) > 20
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("question"), str)
            or not item["question"].strip()
            or not isinstance(item.get("answer"), str)
            or not item["answer"].strip()
            for item in quiz
        )
    ):
        abort(400, "Provide at least one quiz item with a question and answer.")
    if not (
        isinstance(reflection, str) and reflection.strip()
        or isinstance(reflection, list)
        and reflection
        and all(isinstance(item, str) and item.strip() for item in reflection)
    ):
        abort(400, "At least one reflection question is required.")
    audio_url = body.get("audio_url", "")
    audio_status = body.get("audio_status", "NOT_READY")
    if not isinstance(audio_url, str) or not isinstance(audio_status, str):
        abort(400, "Audio URL and status must be text.")
    audio_url = audio_url.strip()
    audio_status = audio_status.strip().upper()
    if audio_status not in {"NOT_READY", "WAITING_PROVIDER_VERIFICATION", "READY"}:
        abort(400, "Unsupported audio status.")
    if audio_url and not (
        (audio_url.startswith("/") and not audio_url.startswith("//"))
        or normalize_url(audio_url)
    ):
        abort(400, "Audio reference must be a relative URL or HTTP(S) URL.")
    if audio_status == "READY" and not audio_url:
        abort(400, "A ready audio asset must have a URL.")
    if audio_status == "READY" and library_story.get(
        "permission_for_audio", ""
    ).strip().upper() != "YES":
        abort(409, "Explicit audio rights permission is required before marking audio ready.")
    story_changed = production.get("myanmar_story", "") != story_text
    production.update({
        "myanmar_title": title.strip(),
        "myanmar_story": story_text,
        "episodes_json": json.dumps(episodes, ensure_ascii=False),
        "quiz_json": json.dumps(quiz, ensure_ascii=False),
        "reflection_json": json.dumps(reflection, ensure_ascii=False),
        "audio_url": "" if story_changed else audio_url,
        "audio_status": "NOT_READY" if story_changed else audio_status,
        "content_review_status": "PENDING",
        "approval_status": "",
        "processing_status": "HUMAN_EDITING",
        "processing_error": "",
    })
    store.write_production(production)
    store.write_episodes(story_id, episodes)
    return jsonify({"ok": True, "processing_status": "HUMAN_EDITING"})


@app.post("/api/admin/story/<story_id>/content-review")
@_admin_api_required
def admin_api_content_review(story_id):
    store = _store()
    production = next(
        (row for row in store.read_records("Story Production") if row.get("story_id") == story_id),
        None,
    )
    if production is None:
        abort(404, "Production draft does not exist.")
    body = request.get_json(silent=True)
    action = body.get("action") if isinstance(body, dict) else None
    if action not in {"approve", "reject"}:
        abort(400, "Choose approve or reject for content review.")
    if action == "approve":
        if not production.get("myanmar_title", "").strip() or not production.get("myanmar_story", "").strip():
            abort(409, "A complete Myanmar title and story are required for review approval.")
        try:
            episodes = json.loads(production.get("episodes_json") or "[]")
            quiz = json.loads(production.get("quiz_json") or "[]")
            reflection = json.loads(production.get("reflection_json") or "[]")
        except json.JSONDecodeError:
            abort(409, "The saved draft contains invalid JSON and requires administrator repair.")
        if not isinstance(episodes, list) or not episodes:
            abort(409, "At least one complete episode is required.")
        if not isinstance(quiz, list) or not quiz or not reflection:
            abort(409, "Quiz and reflection content must be present.")
        if any(
            not isinstance(item, dict)
            or not isinstance(item.get("question"), str)
            or not item["question"].strip()
            or not isinstance(item.get("answer"), str)
            or not item["answer"].strip()
            for item in quiz
        ):
            abort(409, "Quiz items must contain a question and answer.")
        if not (
            isinstance(reflection, str) and reflection.strip()
            or isinstance(reflection, list)
            and reflection
            and all(isinstance(item, str) and item.strip() for item in reflection)
        ):
            abort(409, "Reflection content must contain a non-empty question.")
        full_text = " ".join(production["myanmar_story"].split())
        episode_text = " ".join(
            "".join(
                episode.get("content", "")
                for episode in episodes
                if isinstance(episode, dict)
            ).split()
        )
        if episode_text != full_text or any(
            not isinstance(episode, dict)
            or type(episode.get("episode_number")) is not int
            or episode["episode_number"] != index
            or str(episode.get("complete", "YES")).upper() != "YES"
            for index, episode in enumerate(episodes, 1)
        ):
            abort(409, "Episodes must be complete, ordered, and match the full story.")
    production.update({
        "content_review_status": "APPROVED" if action == "approve" else "REJECTED",
        "processing_status": "CONTENT_APPROVED" if action == "approve" else "REJECTED",
        "approval_status": "",
        "processing_error": "",
    })
    store.write_production(production)
    store.record_processing({
        "processing_id": f"{story_id}-review-{uuid.uuid4().hex[:12]}",
        "story_id": story_id,
        "status": "CONTENT_APPROVED" if action == "approve" else "CONTENT_REJECTED",
        "started_at": utc_now(),
        "completed_at": utc_now(),
        "retry_count": "0",
        "error_details": "",
    })
    return jsonify({
        "ok": True,
        "content_review_status": production["content_review_status"],
        "publication_approval_required": True,
    })

@app.post("/admin/logout")
@_admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@_admin_required
def admin():
    store = _store(initialize=True)
    library = store.read_records("Story Library")
    source_texts = store.read_texts("SOURCE")
    production = {row.get("story_id"): row for row in store.read_records("Story Production")}
    myanmar_texts = store.read_texts("MYANMAR")
    episodes = store.read_records("Story Episodes")
    segmented_episodes = store.read_texts("EPISODES")
    grouped = {}
    for episode in episodes:
        grouped.setdefault(episode.get("story_id"), []).append(episode)

    def episode_order(item):
        try:
            return int(item.get("episode_number", 0))
        except (TypeError, ValueError):
            return 2**31

    stories = []
    for row in library:
        prod = production.get(row.get("story_id"), {})
        if prod and not prod.get("myanmar_story"):
            prod["myanmar_story"] = myanmar_texts.get(row.get("story_id"), "")
        if prod:
            prod["episodes_json"] = _episode_json(
                store, row.get("story_id"), prod, segmented_episodes, episodes
            )
        story = {**row, **prod, "episodes": sorted(
            grouped.get(row.get("story_id"), []),
            key=episode_order,
        )}
        story["source_text"] = (
            story.get("source_text", "") or source_texts.get(row.get("story_id"), "")
        )
        current_episodes = [
            item for item in story["episodes"]
            if item.get("complete", "").upper() == "YES"
        ]
        story["blockers"] = publication_blockers(story, current_episodes)
        stories.append(story)
    return render_template_string(
        ADMIN_HTML,
        stories=stories,
        history=json.dumps(store.read_records("Publishing History"), ensure_ascii=False, indent=2),
    )


@app.post("/admin/story/<story_id>/queue")
@_admin_required
def queue_story(story_id):
    store = _store(initialize=True)
    story = next(
        (row for row in store.read_records("Story Library") if row.get("story_id") == story_id),
        None,
    )
    if story is None:
        abort(404)
    story["source_text"] = request.form.get("source_text", "").strip()
    if not eligible_candidate(story):
        abort(409, "License, rights evidence, reviewer, translation, and AI-processing permissions are required.")
    if not story["source_text"]:
        abort(400, "Rights-cleared source text is required.")
    store.upsert_story(story)
    store.write_production({
        "story_id": story_id,
        "license_review_status": "APPROVED",
        "processing_status": "QUEUED",
        "content_review_status": "PENDING",
        "approval_status": "",
        "processing_error": "",
        "audio_required": "YES",
    })
    return redirect(url_for("admin"))


@app.post("/admin/story/<story_id>")
@_admin_required
def review_story(story_id):
    store = _store(initialize=True)
    story = next(
        (row for row in store.read_records("Story Library") if row.get("story_id") == story_id),
        None,
    )
    if story is None:
        abort(404)
    updates = {
        "story_id": story_id,
        "category": request.form.get("category", "UNCLASSIFIED"),
        "license_evidence": request.form.get("license_evidence", "").strip(),
        "human_reviewer": request.form.get("human_reviewer", "").strip(),
        "rights_cleared": request.form.get("rights_cleared", "NO"),
        "license_status": request.form.get("license_status", "NEEDS_LICENSE_REVIEW"),
        "rights_jurisdiction": request.form.get("rights_jurisdiction", "").strip(),
        "permission_for_translation": request.form.get("permission_for_translation", "NO"),
        "permission_for_ai_processing": request.form.get("permission_for_ai_processing", "NO"),
        "permission_for_publication": request.form.get("permission_for_publication", "NO"),
        "permission_for_audio": request.form.get("permission_for_audio", "NO"),
        "permission_for_commercial_use": request.form.get("permission_for_commercial_use", "NO"),
        "category_evidence": (
            "Human-reviewed category; reviewer: "
            + request.form.get("human_reviewer", "").strip()
        ),
        "review_status": "REVIEWED",
    }
    store.upsert_story({**story, **updates})
    return redirect(url_for("admin"))


@app.post("/admin/story/<story_id>/edit-production")
@_admin_required
def edit_production(story_id):
    store = _store(initialize=True)
    if not any(row.get("story_id") == story_id for row in store.read_records("Story Library")):
        abort(404)
    production = next(
        (row for row in store.read_records("Story Production") if row.get("story_id") == story_id),
        None,
    )
    if production is None:
        abort(404, "Story production draft does not exist.")
    if not production.get("myanmar_story"):
        production["myanmar_story"] = store.read_texts("MYANMAR").get(story_id, "")
    production["episodes_json"] = _episode_json(store, story_id, production)
    if any(
        row.get("story_id") == story_id
        and row.get("publication_status", "").upper() == "PUBLISHED"
        for row in store.read_records("Publishing History")
    ):
        abort(409, "Published stories are immutable in this version; revision publishing is not implemented.")
    for field in ("episodes_json", "quiz_json", "reflection_json"):
        if request.form.get(field):
            try:
                json.loads(request.form[field])
            except json.JSONDecodeError as exc:
                abort(400, f"{field} must contain valid JSON.")
    old_story_text = production.get("myanmar_story", "")
    production.update({
        field: request.form.get(field, production.get(field, ""))
        for field in (
            "myanmar_title", "myanmar_story", "episodes_json", "quiz_json",
            "reflection_json", "audio_url", "audio_status", "audio_required",
        )
    })
    audio_url = production.get("audio_url", "").strip()
    if audio_url and not (
        (audio_url.startswith("/") and not audio_url.startswith("//"))
        or normalize_url(audio_url)
    ):
        abort(400, "Audio reference must be a relative URL or HTTP(S) URL.")
    if production.get("myanmar_story") != old_story_text:
        production["audio_url"] = ""
        production["audio_status"] = "NOT_READY"
    production["content_review_status"] = "PENDING"
    production["approval_status"] = ""
    production["processing_status"] = "HUMAN_EDITING"
    try:
        episode_data = json.loads(production.get("episodes_json") or "[]")
    except json.JSONDecodeError as exc:
        abort(400, "Episodes must be valid JSON.")
    if not isinstance(episode_data, list):
        abort(400, "Episodes must be a JSON array.")
    if not episode_data:
        abort(400, "At least one episode is required for publication review.")
    if any(not isinstance(episode, dict) for episode in episode_data):
        abort(400, "Each episode must be a JSON object.")
    if any(not isinstance(episode.get("content"), str) for episode in episode_data):
        abort(400, "Episode content must be text.")
    if any(len(episode["content"]) > SHEET_CELL_SAFE_LIMIT for episode in episode_data):
        abort(400, "Each episode must fit within Google Sheets' safe cell size.")
    full_text = " ".join(production.get("myanmar_story", "").split())
    episode_text = " ".join(
        "".join(str(episode.get("content", "")) for episode in episode_data).split()
    )
    if not full_text or episode_text != full_text:
        abort(400, "Episode contents must exactly preserve the complete story in order.")
    if any(
        type(episode.get("episode_number")) is not int
        or episode["episode_number"] != index
        or not isinstance(episode.get("title"), str)
        or not episode["title"].strip()
        for index, episode in enumerate(episode_data, 1)
    ):
        abort(400, "Episodes require ordered numbers and non-empty titles.")
    for episode in episode_data:
        episode_audio = str(episode.get("audio_url", "")).strip()
        if episode_audio and not (
            (episode_audio.startswith("/") and not episode_audio.startswith("//"))
            or normalize_url(episode_audio)
        ):
            abort(400, "Episode audio references must be relative or HTTP(S) URLs.")
    store.write_production(production)
    store.write_episodes(story_id, episode_data)
    return redirect(url_for("admin"))


@app.post("/admin/story/<story_id>/publish")
@_admin_required
def approve_and_publish(story_id):
    store = _store(initialize=True)
    story = next(
        (row for row in store.read_records("Story Library") if row.get("story_id") == story_id),
        None,
    )
    if story is None:
        abort(404)
    production = next(
        (row for row in store.read_records("Story Production") if row.get("story_id") == story_id),
        None,
    )
    if production is None:
        abort(409, "Production draft is missing.")
    if not production.get("myanmar_story"):
        production["myanmar_story"] = store.read_texts("MYANMAR").get(story_id, "")
    production["episodes_json"] = _episode_json(store, story_id, production)
    previous_publications = [
        row for row in store.read_records("Publishing History")
        if row.get("story_id") == story_id
    ]
    if any(row.get("publication_status", "").upper() == "PUBLISHED" for row in previous_publications):
        return redirect(url_for("admin"))
    publication_id = f"{story_id}-{uuid.uuid4().hex[:12]}"
    retry_count = str(len(previous_publications))
    if os.environ.get("PYONPYIN_PUBLISHING_ENABLED", "").lower() != "true":
        store.record_publication({
            "publication_id": publication_id,
            "story_id": story_id,
            "published_title": production.get("myanmar_title", ""),
            "publication_status": "DISABLED",
            "retry_count": retry_count,
            "error_details": "Publishing is disabled by default; enable it explicitly after setup.",
            "approved_by": request.form.get("approved_by", "").strip(),
        })
        abort(503, "Publishing is disabled. Set PYONPYIN_PUBLISHING_ENABLED=true to enable.")
    production.update({
        "content_review_status": request.form.get("content_review_status", ""),
        "approval_status": request.form.get("approval_status", ""),
    })
    episodes = [
        row for row in store.read_records("Story Episodes")
        if row.get("story_id") == story_id and row.get("complete", "").upper() == "YES"
    ]
    production["audio_required"] = production.get("audio_required", "NO")
    story.update(production)
    blockers = publication_blockers(
        story,
        episodes,
        require_audio=production["audio_required"].strip().upper() == "YES",
    )
    if blockers:
        store.record_publication({
            "publication_id": publication_id,
            "story_id": story_id,
            "published_title": production.get("myanmar_title", ""),
            "publication_status": "BLOCKED",
            "retry_count": retry_count,
            "error_details": " ".join(blockers),
            "approved_by": request.form.get("approved_by", "").strip(),
        })
        abort(409, "Publication blocked: " + " ".join(blockers))
    if not request.form.get("approved_by", "").strip():
        abort(400, "An approving human's name is required.")
    base_url = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    parsed_base_url = urlsplit(base_url)
    if (
        not parsed_base_url.hostname
        or parsed_base_url.username
        or parsed_base_url.password
        or parsed_base_url.query
        or parsed_base_url.fragment
        or parsed_base_url.path not in {"", "/"}
        or parsed_base_url.scheme.lower() not in {"https", "http"}
        or (
            parsed_base_url.scheme.lower() == "http"
            and parsed_base_url.hostname not in {"localhost", "127.0.0.1"}
        )
    ):
        abort(503, "Set PUBLIC_BASE_URL to a configured HTTPS website before publishing.")
    # Site output is the public catalogue; only the approved endpoint includes this record.
    store.write_production(production)
    store.record_publication({
        "publication_id": publication_id,
        "story_id": story_id,
        "published_title": production.get("myanmar_title", ""),
        "website_url": base_url + url_for("public_story", story_id=story_id),
        "published_at": utc_now(),
        "episode_count": str(len(episodes)),
        "publication_status": "PUBLISHED",
        "retry_count": retry_count,
        "error_details": "",
        "approved_by": request.form["approved_by"].strip(),
    })
    return redirect(url_for("admin"))


@app.get("/")
def public_home():
    store = _store()
    history = {
        item.get("story_id") for item in store.read_records("Publishing History")
        if item.get("publication_status", "").upper() == "PUBLISHED"
    }
    production = {
        item.get("story_id"): item for item in store.read_records("Story Production")
    }
    myanmar_texts = store.read_texts("MYANMAR")
    segmented_episodes = store.read_texts("EPISODES")
    episode_rows = store.read_records("Story Episodes")
    stories = []
    for record in store.read_records("Story Library"):
        if record.get("story_id") not in history:
            continue
        draft = production.get(record.get("story_id"), {})
        if not draft.get("myanmar_story"):
            draft["myanmar_story"] = myanmar_texts.get(record.get("story_id"), "")
        draft["episodes_json"] = _episode_json(
            store, record.get("story_id"), draft, segmented_episodes, episode_rows
        )
        episodes = json.loads(draft.get("episodes_json") or "[]")
        if record.get("category", "").upper() not in {"CHILDREN", "ADULT"}:
            continue
        if publication_blockers(
            {**record, **draft},
            episodes,
            require_audio=draft.get("audio_required", "").upper() == "YES",
        ):
            continue
        if draft.get("content_review_status", "").upper() != "APPROVED":
            continue
        if draft.get("approval_status", "").upper() != "APPROVED":
            continue
        draft["category"] = record.get("category", "")
        draft["story_id"] = record.get("story_id", "")
        draft["description"] = (draft.get("myanmar_story", "")[:180] + "…")
        draft["episodes"] = json.loads(draft.get("episodes_json") or "[]")
        stories.append(draft)
    query = request.args.get("q", "").strip()
    if query:
        stories = [story for story in stories if query.casefold() in (
            story.get("myanmar_title", "") + story.get("myanmar_story", "")
        ).casefold()]
    return render_template_string(PUBLIC_HTML, stories=stories, query=query)


@app.get("/story/<story_id>")
def public_story(story_id):
    store = _store()
    publication = next(
        (
            item for item in store.read_records("Publishing History")
            if item.get("story_id") == story_id
            and item.get("publication_status", "").upper() == "PUBLISHED"
        ),
        None,
    )
    library = next(
        (item for item in store.read_records("Story Library") if item.get("story_id") == story_id),
        None,
    )
    draft = next(
        (item for item in store.read_records("Story Production") if item.get("story_id") == story_id),
        None,
    )
    if not publication or not library or not draft:
        abort(404)
    if not draft.get("myanmar_story"):
        draft["myanmar_story"] = store.read_texts("MYANMAR").get(story_id, "")
    draft["episodes_json"] = _episode_json(store, story_id, draft)
    episodes = json.loads(draft.get("episodes_json") or "[]")
    if publication_blockers(
        {**library, **draft},
        episodes,
        require_audio=draft.get("audio_required", "").upper() == "YES",
    ):
        abort(404)
    return render_template_string(
        """<!doctype html><html lang="my"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
        <title>{{ story.myanmar_title }}</title><style>body{font:1.1rem/2 'Myanmar Text','Noto Sans Myanmar',sans-serif;
        max-width:850px;margin:2rem auto;padding:0 1rem;color:#193b3c;background:#fff9ed}
        article{background:white;padding:2rem;border-radius:1rem}pre{white-space:pre-wrap;font:inherit}
        audio{width:100%}</style><a href="/">← ပုံပြင်များသို့</a><article><h1>{{ story.myanmar_title }}</h1>
        <pre>{{ story.myanmar_story }}</pre>{% if story.audio_url and story.audio_status == 'READY' %}<audio controls preload="none" src="{{ story.audio_url }}"></audio>{% endif %}
        {% for ep in episodes %}<h2 id="episode-{{ ep.episode_number }}">{{ ep.episode_number }}. {{ ep.title }}</h2>
        <nav>{% if not loop.first %}<a href="#episode-{{ ep.episode_number|int - 1 }}">← Previous</a>{% endif %}
        {% if not loop.last %}<a href="#episode-{{ ep.episode_number|int + 1 }}">Next →</a>{% endif %}</nav>
        <pre>{{ ep.content }}</pre>{% if ep.audio_url and ep.audio_status == 'READY' %}<audio controls preload="none" src="{{ ep.audio_url }}"></audio>{% endif %}
        {% endfor %}</article></html>""",
        story=draft,
        episodes=episodes,
    )


@app.get("/api/stories")
def public_stories():
    store = _store()
    published_ids = {
        item.get("story_id") for item in store.read_records("Publishing History")
        if item.get("publication_status", "").upper() == "PUBLISHED"
    }
    result = []
    production = store.read_records("Story Production")
    by_id = {item.get("story_id"): item for item in production}
    myanmar_texts = store.read_texts("MYANMAR")
    segmented_episodes = store.read_texts("EPISODES")
    episode_rows = store.read_records("Story Episodes")
    for record in store.read_records("Story Library"):
        draft = by_id.get(record.get("story_id"), {})
        if not draft.get("myanmar_story"):
            draft["myanmar_story"] = myanmar_texts.get(record.get("story_id"), "")
        draft["episodes_json"] = _episode_json(
            store, record.get("story_id"), draft, segmented_episodes, episode_rows
        )
        if record.get("story_id") not in published_ids:
            continue
        episodes = json.loads(draft.get("episodes_json") or "[]")
        if publication_blockers(
            {**record, **draft},
            episodes,
            require_audio=draft.get("audio_required", "").upper() == "YES",
        ):
            continue
        public_episodes = [
            {
                **episode,
                "audio_url": (
                    episode.get("audio_url", "")
                    if episode.get("audio_status", "").strip().upper() == "READY"
                    else ""
                ),
            }
            for episode in episodes
            if isinstance(episode, dict)
        ]
        result.append({
            "story_id": record["story_id"],
            "category": record["category"],
            "title": draft.get("myanmar_title", ""),
            "story": draft.get("myanmar_story", ""),
            "episodes": public_episodes,
            "audio_url": (
                draft.get("audio_url", "")
                if draft.get("audio_status", "").upper() == "READY" else ""
            ),
        })
    return jsonify(result)


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "publishing_enabled": os.environ.get("PYONPYIN_PUBLISHING_ENABLED", "").lower() == "true",
        "human_approval_required": True,
    })


if __name__ == "__main__":
    if not os.environ.get("PYONPYIN_ADMIN_PASSWORD"):
        raise SystemExit("Set PYONPYIN_ADMIN_PASSWORD before starting the dashboard.")
    if not os.environ.get("PYONPYIN_SESSION_SECRET"):
        raise SystemExit("Set PYONPYIN_SESSION_SECRET before starting the dashboard.")
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))
