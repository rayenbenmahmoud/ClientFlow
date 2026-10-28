"""Capture README screenshots from a freshly seeded demo (read-only: creates no data).

Run `python manage.py seed_demo --reset` first, start backend (:8000) and frontend (:5173), then:
    python scripts/capture_screenshots.py [--password ClientFlow-Demo-2026]
"""

import argparse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

BASE = "http://127.0.0.1:5173"


def login(page: Page, user: str, password: str):
    page.goto(f"{BASE}/login")
    page.get_by_label("Username").fill(user)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_selector("text=Welcome back")


def snap(page: Page, out: Path, name: str, full=False, wait=1600):
    page.wait_for_timeout(wait)  # let chart animations finish
    page.screenshot(path=str(out / f"{name}.png"), full_page=full)
    print("saved", name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/screenshots")
    ap.add_argument("--password", default="ClientFlow-Demo-2026")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{BASE}/login")
        snap(page, out, "01-login", wait=300)
        login(page, "manager", a.password)
        page.wait_for_selector("svg.recharts-surface")
        snap(page, out, "02-dashboard", full=True)

        page.get_by_role("link", name="Leads").first.click()
        page.wait_for_selector("table")
        snap(page, out, "03-leads", wait=400)

        page.get_by_role("link", name="Deals").first.click()
        page.wait_for_selector("section[aria-label='New stage'] li")
        snap(page, out, "04-pipeline", wait=400)

        page.locator("section[aria-label='Negotiation stage'] li a").first.click()
        page.wait_for_selector("text=Stage history")
        snap(page, out, "05-deal-detail", full=True, wait=500)

        page.get_by_role("link", name="Contacts").first.click()
        page.wait_for_selector("table")
        snap(page, out, "06-contacts", wait=400)
        page.locator("tbody tr a").first.click()
        page.wait_for_selector("text=Activity history")
        snap(page, out, "07-contact-detail", full=True, wait=500)

        page.get_by_role("link", name="Tasks").first.click()
        page.get_by_role("button", name="Calendar").click()
        page.wait_for_selector("[role=gridcell]")
        snap(page, out, "08-tasks-calendar", wait=500)

        page.get_by_role("link", name="Dashboard").first.click()
        page.get_by_role("button", name="Notifications", exact=False).click()
        page.wait_for_selector("text=Mark all read")
        snap(page, out, "09-notifications", wait=500)

        m = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2).new_page()
        login(m, "manager", a.password)
        m.wait_for_selector("svg.recharts-surface")
        snap(m, out, "10-mobile-dashboard")
        m.get_by_role("button", name="Open menu").click()
        snap(m, out, "11-mobile-menu", wait=300)
        m.get_by_role("link", name="Deals").first.click()
        m.wait_for_selector("section[aria-label='New stage']")
        snap(m, out, "12-mobile-pipeline", wait=400)
        b.close()


if __name__ == "__main__":
    main()
