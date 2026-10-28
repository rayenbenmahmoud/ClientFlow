"""Browser smoke test + screenshot generator (Playwright, Chromium).

Prerequisites: backend running on :8000 with seeded demo data, frontend dev server on :5173.
Usage:  python scripts/e2e_browser.py [--shots docs/screenshots] [--password ClientFlow-Demo-2026]

It logs in as different roles, drives the main flows, asserts on visible results, fails on any
console error / failed API call, and saves screenshots used in the README.
"""

import argparse
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

BASE = "http://127.0.0.1:5173"
problems: list[str] = []
results: list[str] = []


def check(name: str, ok: bool, detail: str = ""):
    results.append(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail and not ok else ''}")
    if not ok:
        problems.append(name)


def watch(page: Page):
    def on_console(m):
        expected = "favicon" in m.text or re.search(r"Failed to load resource: .* status of 4\d\d", m.text)
        if m.type == "error" and not expected:
            problems.append(f"console error: {m.text}")

    page.on("console", on_console)
    page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
    page.on(
        "response",
        lambda r: problems.append(f"API {r.status} {r.request.method} {r.url}")
        if "/api/" in r.url and r.status >= 500
        else None,
    )


def login(page: Page, user: str, password: str):
    page.goto(f"{BASE}/login")
    page.get_by_label("Username").fill(user)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url(lambda url: "/login" not in url)  # returns to the page that required login, else "/"
    page.goto(f"{BASE}/")
    expect(page.get_by_text("Welcome back")).to_be_visible()


def shot(page: Page, folder: Path, name: str, full=False):
    page.wait_for_timeout(500)
    page.screenshot(path=str(folder / f"{name}.png"), full_page=full)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", default="docs/screenshots")
    ap.add_argument("--password", default="ClientFlow-Demo-2026")
    args = ap.parse_args()
    out = Path(args.shots)
    out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        watch(page)

        # ---- login screen + invalid credentials ----
        page.goto(f"{BASE}/login")
        shot(page, out, "01-login")
        page.get_by_label("Username").fill("manager")
        page.get_by_label("Password").fill("wrong-password")
        page.get_by_role("button", name="Sign in").click()
        expect(page.get_by_text("Incorrect username or password")).to_be_visible()
        check("bad login shows an error", True)
        # protected route redirects when logged out
        page.goto(f"{BASE}/leads")
        page.wait_for_url(re.compile("/login"))
        check("protected route redirects to login", "/login" in page.url)

        # ---- manager: dashboard ----
        login(page, "manager", args.password)
        page.wait_for_selector("svg.recharts-surface")
        check("dashboard shows KPI cards", page.get_by_text("Pipeline value").first.is_visible())
        check("dashboard shows pipeline chart", page.locator("svg.recharts-surface").count() >= 1)
        shot(page, out, "02-dashboard", full=True)

        # ---- leads: overdue badges, create lead -> auto task ----
        page.get_by_role("link", name="Leads").first.click()
        expect(page.get_by_role("heading", name="Leads", exact=True)).to_be_visible()
        page.wait_for_selector("table")
        check("leads table lists overdue follow-ups", page.get_by_text(re.compile(r"Overdue")).count() > 0)
        shot(page, out, "03-leads")
        page.get_by_role("button", name="New lead").click()
        page.get_by_label("First name").fill("Quinn")
        page.get_by_label("Last name").fill("Playwright")
        page.get_by_label("Company").fill("Playwright Bakery")
        page.get_by_role("button", name="Create lead").click()
        expect(page.get_by_text("Lead created.")).to_be_visible()
        page.get_by_role("link", name="Tasks").first.click()
        page.get_by_placeholder("Search tasks...").fill("Quinn Playwright")
        expect(page.get_by_text("Follow up with Quinn Playwright")).to_be_visible()
        check("creating a lead creates a follow-up task", True)

        # ---- form validation: server errors appear next to fields ----
        page.get_by_role("link", name="Contacts").first.click()
        page.get_by_role("button", name="New contact").click()
        page.get_by_label("First name").fill("Valid")
        page.get_by_label("Last name").fill("Person")
        page.get_by_label("Phone").fill("not a phone")
        page.get_by_role("button", name="Create contact").click()
        check("invalid phone is rejected with a field message", page.get_by_text(re.compile("valid phone number")).first.is_visible())
        page.keyboard.press("Escape")

        # ---- lead conversion ----
        page.get_by_role("link", name="Leads").first.click()
        page.get_by_placeholder("Search name, company, email...").fill("Quinn")
        page.get_by_role("link", name="Quinn Playwright").click()
        page.get_by_role("button", name="Convert to deal").click()
        page.get_by_label("Amount (USD)").fill("4200")
        page.get_by_role("button", name="Convert to deal").last.click()
        expect(page.get_by_text("Lead converted")).to_be_visible()
        page.wait_for_url(re.compile(r"/deals/\d+"))
        check("lead conversion opens the new deal", "/deals/" in page.url)
        expect(page.get_by_text("Created in New")).to_be_visible()
        check("converted deal starts in New with history", True)

        # ---- deal detail: valid + invalid transitions ----
        expect(page.get_by_role("button", name="Lost", exact=True)).to_be_visible()
        check("New deal offers only Qualified and Lost", page.get_by_role("button", name="Proposal", exact=True).count() == 0)
        page.get_by_role("button", name="Qualified", exact=True).click()
        expect(page.get_by_text(re.compile("moved to Qualified"))).to_be_visible()
        page.get_by_role("button", name="Lost", exact=True).click()
        page.get_by_role("button", name="Mark as lost").click()
        dialog = page.get_by_role("dialog")
        blocked = dialog.is_visible() and page.get_by_label("Why was it lost?").evaluate("e => !e.checkValidity()")
        check("losing a deal requires a reason (form blocks empty submit)", bool(blocked))
        page.get_by_label("Why was it lost?").fill("Chose a competitor")
        page.get_by_role("button", name="Mark as lost").click()
        expect(page.get_by_text("Deal marked as lost.")).to_be_visible()
        check("lost reason is displayed", page.get_by_text("Chose a competitor").first.is_visible())
        shot(page, out, "06-deal-detail", full=True)

        # ---- pipeline board: move via card menu ----
        page.get_by_role("link", name="Deals").first.click()
        expect(page.get_by_role("heading", name="Pipeline", exact=True)).to_be_visible()
        page.wait_for_selector("section[aria-label='New stage'] li")
        shot(page, out, "04-pipeline")
        sel = page.locator("section[aria-label='New stage'] select").first
        sel.select_option("qualified")
        expect(page.get_by_text(re.compile("moved to Qualified")).first).to_be_visible()
        check("board 'Move to' menu changes stage", True)
        # drag & drop: qualified -> proposal
        card = page.locator("section[aria-label='Qualified stage'] li[draggable='true']").first
        title = card.locator("a").inner_text()
        card.drag_to(page.locator("section[aria-label='Proposal stage']"))
        page.wait_for_timeout(800)
        in_proposal = page.locator("section[aria-label='Proposal stage']").get_by_text(title).count() > 0
        check("drag and drop moves a deal between stages", in_proposal)
        page.get_by_role("button", name="Table").click()
        page.wait_for_selector("table")
        shot(page, out, "05-deals-table")

        # ---- contacts / company detail ----
        page.get_by_role("link", name="Contacts").first.click()
        page.wait_for_selector("table")
        shot(page, out, "07-contacts")
        page.locator("tbody tr a").first.click()
        expect(page.get_by_text("Activity history")).to_be_visible()
        page.get_by_role("button", name="Log interaction").click()
        page.get_by_label("Subject").fill("Intro call logged by e2e")
        page.get_by_role("button", name="Log interaction").last.click()
        expect(page.get_by_text("Interaction logged.")).to_be_visible()
        check("interaction appears in activity history", page.get_by_text("Intro call logged by e2e").is_visible())
        shot(page, out, "08-contact-detail", full=True)

        # ---- tasks calendar ----
        page.get_by_role("link", name="Tasks").first.click()
        page.get_by_role("button", name="Calendar").click()
        page.wait_for_selector("[role=gridcell]")
        shot(page, out, "09-tasks-calendar")
        page.get_by_role("button", name="List").click()
        page.wait_for_selector("table")

        # ---- notifications ----
        page.get_by_role("link", name="Dashboard").first.click()
        page.get_by_role("button", name=re.compile("Notifications")).click()
        page.wait_for_selector("text=Mark all read")
        shot(page, out, "10-notifications")
        page.keyboard.press("Escape")

        # ---- CSV export download ----
        page.get_by_role("link", name="Companies").first.click()
        page.wait_for_selector("table")
        with page.expect_download() as dl:
            page.get_by_role("button", name="Export CSV").click()
        check("CSV export downloads a file", dl.value.suggested_filename.endswith(".csv"))

        # ---- mobile layout ----
        m = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        mp = m.new_page()
        watch(mp)
        login(mp, "manager", args.password)
        mp.wait_for_selector("svg.recharts-surface")
        check("mobile: sidebar is hidden behind a menu button", mp.get_by_role("button", name="Open menu").is_visible())
        overflow = mp.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
        check("mobile: dashboard has no horizontal page scroll", not overflow)
        shot(mp, out, "11-mobile-dashboard")
        mp.get_by_role("button", name="Open menu").click()
        shot(mp, out, "12-mobile-menu")
        mp.get_by_role("link", name="Deals").first.click()
        mp.wait_for_selector("section[aria-label='New stage']")
        shot(mp, out, "13-mobile-pipeline")
        mp.get_by_role("button", name="Open menu").click()
        mp.get_by_role("link", name="Leads").first.click()
        mp.wait_for_selector("table")
        overflow = mp.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
        check("mobile: leads table scrolls inside its container", not overflow)
        shot(mp, out, "14-mobile-leads")
        m.close()

        # ---- role-based access: sales rep ----
        r = browser.new_context(viewport={"width": 1440, "height": 900})
        rp = r.new_page()
        watch(rp)
        login(rp, "rep", args.password)
        check("rep dashboard is personal", rp.get_by_text("Your personal overview").is_visible())
        rp.get_by_role("link", name="Leads").first.click()
        rp.wait_for_selector("table")
        check("rep has no Owner filter", rp.get_by_label("Owner").count() == 0)
        rp.get_by_role("link", name="Companies").first.click()
        rp.wait_for_selector("table")
        check("rep cannot delete companies (no Delete buttons)", rp.get_by_role("button", name=re.compile("^Delete")).count() == 0)
        r.close()
        browser.close()

    print("\n".join(results))
    if problems:
        print("\nPROBLEMS:")
        print("\n".join(f" - {x}" for x in dict.fromkeys(problems)))
        sys.exit(1)
    print(f"\nAll {len(results)} browser checks passed; screenshots in {out}/")


if __name__ == "__main__":
    main()
