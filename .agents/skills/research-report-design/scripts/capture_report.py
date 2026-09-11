#!/usr/bin/env python3
"""Capture research-report screenshots and browser diagnostics.

This utility records observations, not a visual/accessibility/statistical pass.
Run a development server separately and inspect the saved images yourself.
Requires: python -m pip install playwright && python -m playwright install chromium
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

VIEWPORTS = (
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Local or explicitly authorized HTTP(S) report URL")
    parser.add_argument("--out", type=Path, required=True, help="Destination directory")
    parser.add_argument("--ready-selector", help="Selector indicating real report content is ready")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--browser-executable", help="Optional path to an already installed Chromium")
    args = parser.parse_args()
    parts = urlsplit(args.url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        parser.error("--url must be an HTTP(S) URL")
    if parts.username or parts.password:
        parser.error("Do not include credentials in --url")
    if args.timeout_ms < 1000:
        parser.error("--timeout-ms must be at least 1000")
    if args.browser_executable and not Path(args.browser_executable).is_file():
        parser.error("--browser-executable does not name an existing file")
    return args


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout
    except ImportError:
        print("Playwright is missing. Install with: python -m pip install playwright", file=sys.stderr)
        print("Then install a browser: python -m playwright install chromium", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_url": args.url,
        "ready_selector": args.ready_selector,
        "kind": "browser-observations-not-a-quality-certification",
        "notes": [
            "Screenshots require manual inspection; successful capture is not design acceptance.",
            "Horizontal document overflow is a diagnostic, not a complete layout test.",
            "Console/network observations may include third-party or development-server noise.",
            "Capture does not validate aggregate values, statistical definitions, or accessibility compliance.",
            "Review captured content before sharing; screenshots may contain private report data.",
        ],
        "captures": [],
    }
    failed = False
    try:
        with sync_playwright() as engine:
            options: dict[str, Any] = {"headless": True}
            if args.browser_executable:
                options["executable_path"] = args.browser_executable
            browser = engine.chromium.launch(**options)
            try:
                for name, width, height in VIEWPORTS:
                    entry: dict[str, Any] = {
                        "viewport_name": name,
                        "viewport": {"width": width, "height": height},
                        "console_errors": [], "page_errors": [],
                        "failed_requests": [], "http_errors": [], "warnings": [],
                    }
                    # A fresh browser context prevents filters/storage from leaking across captures.
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        device_scale_factor=1,
                        reduced_motion="reduce",
                    )
                    page = context.new_page()
                    page.set_default_timeout(args.timeout_ms)
                    page.on("console", lambda message, e=entry: e["console_errors"].append(message.text)
                            if message.type == "error" else None)
                    page.on("pageerror", lambda error, e=entry: e["page_errors"].append(str(error)))
                    page.on("requestfailed", lambda request, e=entry: e["failed_requests"].append(
                        {"url": request.url, "failure": request.failure}))
                    page.on("response", lambda response, e=entry: e["http_errors"].append(
                        {"url": response.url, "status": response.status}) if response.status >= 400 else None)
                    try:
                        response = page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout_ms)
                        entry["main_response_status"] = response.status if response else None
                        if response and response.status >= 400:
                            raise RuntimeError(f"Main document returned HTTP {response.status}")
                        if args.ready_selector:
                            page.locator(args.ready_selector).first.wait_for(state="visible")
                        else:
                            entry["warnings"].append("No ready selector supplied; asynchronous report content may be incomplete.")
                        try:
                            page.wait_for_function("!document.fonts || document.fonts.status === 'loaded'", timeout=5000)
                        except BrowserTimeout:
                            entry["warnings"].append("Fonts were not settled within 5 seconds; verify fallback rendering.")
                        # Let layout flush without relying on never-ending network-idle heuristics.
                        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                        entry["final_url"] = page.url
                        entry["title"] = page.title()
                        entry["dom"] = page.evaluate("""() => {
                            const root = document.documentElement;
                            const rect = el => { const r = el.getBoundingClientRect();
                                return {x:r.x, y:r.y, width:r.width, height:r.height}; };
                            return {
                                document_width: root.scrollWidth,
                                viewport_width: root.clientWidth,
                                document_height: root.scrollHeight,
                                document_horizontal_overflow: root.scrollWidth > root.clientWidth + 1,
                                h1: [...document.querySelectorAll('h1')].map(el => ({text:el.textContent.trim(), ...rect(el)})),
                                headings: [...document.querySelectorAll('h2,h3')].slice(0,40).map(el => ({level:el.tagName,text:el.textContent.trim(),...rect(el)})),
                                figures: [...document.querySelectorAll('figure,[role="img"],.snapshot-card')].slice(0,20).map(el => ({tag:el.tagName,label:el.getAttribute('aria-label'),...rect(el)}))
                            };
                        }""")
                        viewport_file = args.out / f"{name}-viewport.png"
                        full_file = args.out / f"{name}-full.png"
                        page.screenshot(path=str(viewport_file), full_page=False, animations="disabled")
                        page.screenshot(path=str(full_file), full_page=True, animations="disabled")
                        entry["screenshots"] = {"viewport": viewport_file.name, "full_page": full_file.name}
                        entry["capture_status"] = "captured-awaiting-human-review"
                    except Exception as exc:
                        failed = True
                        entry["capture_status"] = "failed"
                        entry["error"] = str(exc)
                    finally:
                        context.close()
                        report["captures"].append(entry)
            finally:
                browser.close()
    except Exception as exc:
        failed = True
        report["fatal_error"] = str(exc)
    report["visual_acceptance"] = "pending-manual-inspection"
    write_json(args.out / "capture-report.json", report)
    print(f"Saved observations: {args.out / 'capture-report.json'}")
    if failed:
        print("At least one capture failed. Inspect the JSON; do not present it as completed visual QA.", file=sys.stderr)
        return 1
    print("Screenshots captured. Inspect them and test interactions before accepting the design.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
