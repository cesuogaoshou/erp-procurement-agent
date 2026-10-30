"""Capture current UI screenshots for the course report."""
from pathlib import Path
import json
import time

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/generated/screenshots_current"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:5173"
API = "http://127.0.0.1:8000"


def login_session() -> dict:
    response = httpx.post(f"{API}/auth/login", json={"username": "buyer", "password": "buyer-pass"}, timeout=10)
    response.raise_for_status()
    return response.json()


def main() -> None:
    session = login_session()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
        page = context.new_page()
        page.add_init_script(
            "localStorage.setItem('erp-session', " + json.dumps(json.dumps(session, ensure_ascii=False)) + ");"
        )
        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "01-agent-procurement.png"))

        # Run a real Agent procurement request so the screenshot shows the
        # complete human-readable result and draft summary.
        prompt = "请买120件标准轴承，20天内到货，总预算5000元，生成草稿等待审批。"
        page.locator("#procurement-request").fill(prompt)
        budget = page.locator('input[aria-label="确认整单预算（元）"]')
        budget.fill("5000")
        page.get_by_role("button", name="分析并准备采购").click()
        try:
            page.wait_for_selector("text=草稿已生成", timeout=120_000)
        except Exception:
            # Keep a screenshot of the controlled result even if the model
            # returns a clarification in this environment.
            page.wait_for_selector(".business-result", timeout=10_000)
        page.wait_for_timeout(1500)
        page.screenshot(path=str(OUT / "02-agent-result.png"))

        # Analysis page: default material is MAT-001; click 分析 and wait for
        # the two ECharts canvases.
        page.locator(".el-menu-item").filter(has_text="数据分析").click()
        page.wait_for_timeout(700)
        page.get_by_role("button", name="分析", exact=True).click()
        page.wait_for_selector("canvas", timeout=120_000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT / "03-analysis-charts.png"))

        # Approval list and detail dialog, including the new edit action.
        page.locator(".el-menu-item").filter(has_text="采购审批").click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "04-approval-list.png"))
        detail_buttons = page.get_by_role("button", name="查看明细")
        if detail_buttons.count() > 0:
            detail_buttons.first.click()
            page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / "05-approval-detail.png"))
            edit = page.get_by_role("button", name="编辑草稿")
            if edit.count() > 0:
                edit.first.click()
                page.wait_for_timeout(700)
                page.screenshot(path=str(OUT / "06-draft-edit.png"))
                cancel = page.get_by_role("button", name="取消")
                if cancel.count() > 0:
                    cancel.first.click()
            close = page.get_by_role("button", name="关闭明细")
            if close.count() > 0:
                close.first.click()

        # Execution records and one persisted trace.
        page.locator(".el-menu-item").filter(has_text="执行记录").click()
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT / "07-execution-records.png"))
        rows = page.locator(".el-table__row")
        if rows.count() > 0:
            rows.first.click()
            page.wait_for_timeout(1200)
            page.screenshot(path=str(OUT / "08-execution-traces.png"))

        browser.close()


if __name__ == "__main__":
    main()
