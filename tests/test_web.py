"""UI delivery, security headers, and static rules the frontend must obey."""

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hcm_ai.config import get_settings
from hcm_ai.main import WEB_DIR, create_app
from hcm_ai.ratelimit import get_rate_limiter

ROOT = Path(__file__).parent.parent
WEB_FILES = [p for p in WEB_DIR.rglob("*") if p.is_file()]
JS_FILES = [p for p in WEB_FILES if p.suffix == ".js"]


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'w.db'}")
    get_settings.cache_clear()
    get_rate_limiter.cache_clear()
    return TestClient(create_app())


# ---- delivery ----


def test_root_serves_the_app_shell(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert '<div id="app">' in r.text and 'type="module"' in r.text


def test_assets_are_served_with_correct_types(client: TestClient) -> None:
    assert "javascript" in client.get("/js/main.js").headers["content-type"]
    assert "text/css" in client.get("/css/app.css").headers["content-type"]
    assert client.get("/js/nope.js").status_code == 404


def test_api_routes_win_over_static_files(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/ai/chat", json={"message": "x"}).status_code == 401


def test_ui_has_a_strict_csp_and_hardening_headers(client: TestClient) -> None:
    h = client.get("/").headers
    csp = h["content-security-policy"]
    for directive in (
        "default-src 'self'",
        "script-src 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
    ):
        assert directive in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert h["x-frame-options"] == "DENY"


def test_api_responses_are_never_cached(client: TestClient) -> None:
    assert client.get("/health").headers["cache-control"] == "no-store"
    assert (
        client.post("/auth/demo-login", json={"role": "HR"}).headers["cache-control"] == "no-store"
    )


# ---- source rules (enforce the constitution's frontend section) ----


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_js_never_uses_unsafe_sinks(path: Path) -> None:
    # Comments may *mention* the banned APIs; only real code counts.
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
    forbidden = (
        r"innerHTML|outerHTML|insertAdjacentHTML|document\.write"
        r"|\beval\s*\(|new Function|setTimeout\(\s*[\"']"
    )
    assert not re.search(forbidden, code), f"unsafe DOM/code sink in {path.name}"


@pytest.mark.parametrize("path", WEB_FILES, ids=lambda p: p.name)
def test_ui_has_no_external_hosts_or_provider_references(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    assert not re.search(r"https?://", text), "no CDN/external URLs: the CSP is same-origin"
    for provider in ("groq", "openai", "gemini", "googleapis"):
        assert provider not in text, "the browser must never talk to an AI provider"


def test_html_has_no_inline_script_style_or_handlers() -> None:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html)
    assert "<style" not in html and "style=" not in html
    assert not re.search(r"\son[a-z]+\s*=", html)


def test_js_never_sets_inline_style_attributes() -> None:
    for path in JS_FILES:
        assert 'setAttribute("style"' not in path.read_text(encoding="utf-8"), path.name


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
def test_node_unit_tests_for_ui_logic_pass() -> None:
    node = shutil.which("node") or "node"
    result = subprocess.run(  # noqa: S603
        [node, "--test", "web_tests/*.test.mjs"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
