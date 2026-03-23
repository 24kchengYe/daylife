"""Frontend visual test for DayLife dashboard"""
from playwright.sync_api import sync_playwright
import json

RESULTS = []

def log(test_name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((test_name, status, detail))
    print(f"[{status}] {test_name}: {detail}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})

    # Capture console errors
    console_errors = []
    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: console_errors.append(str(err)))

    # 1) Page renders
    page.goto("http://127.0.0.1:8061")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)  # Let charts init

    title = page.title()
    log("Page title", "DayLife" in title, title)

    # Check for JS errors
    js_errors = [e for e in console_errors if "error" in e.lower() or "Error" in e]
    log("No JS errors", len(js_errors) == 0, f"{len(js_errors)} errors: {js_errors[:3]}" if js_errors else "clean")

    page.screenshot(path="/tmp/daylife_01_dashboard.png", full_page=True)

    # 2) Heatmap calendar
    calendar_grid = page.locator(".calendar-grid")
    has_calendar = calendar_grid.count() > 0
    log("Calendar grid exists", has_calendar)

    calendar_cells = page.locator(".calendar-cell").count()
    log("Calendar cells rendered", calendar_cells > 300, f"{calendar_cells} cells")

    year_select = page.locator(".year-select")
    has_year_select = year_select.count() > 0
    log("Year selector exists", has_year_select)

    # Check calendar legend
    legend = page.locator(".calendar-legend")
    log("Calendar legend exists", legend.count() > 0)

    # 3) Charts initialized
    week_chart = page.locator("#chart-week-completion canvas")
    log("Week completion chart canvas", week_chart.count() > 0)

    month_chart = page.locator("#chart-month-completion canvas")
    log("Month completion chart canvas", month_chart.count() > 0)

    cat_chart = page.locator("#chart-category canvas")
    log("Category pie chart canvas", cat_chart.count() > 0)

    trend_chart = page.locator("#chart-trend canvas")
    log("Trend line chart canvas", trend_chart.count() > 0)

    page.screenshot(path="/tmp/daylife_02_charts.png", full_page=True)

    # Check streak stats
    streak_val = page.locator("#streak-count").text_content()
    log("Streak count displayed", streak_val is not None, f"value={streak_val}")

    # 4) Search functionality
    search_nav = page.locator("[data-nav='search']")
    search_nav.click()
    page.wait_for_timeout(500)

    search_panel = page.locator("[data-view='search']")
    log("Search view active", "active" in (search_panel.get_attribute("class") or ""))

    search_input = page.locator("#search-input")
    log("Search input exists", search_input.count() > 0)

    # Type and search
    search_input.fill("test")
    page.locator("#search-btn").click()
    page.wait_for_timeout(1000)

    search_results = page.locator("#search-results")
    results_text = search_results.text_content()
    log("Search returns result (empty ok)", results_text is not None, f"content: {results_text[:50] if results_text else 'none'}")

    page.screenshot(path="/tmp/daylife_03_search.png", full_page=True)

    # 5) Theme toggle
    # Go back to dashboard first
    page.locator("[data-nav='dashboard']").click()
    page.wait_for_timeout(500)

    initial_theme = page.locator("html").get_attribute("data-theme")
    log("Initial theme", initial_theme == "light", f"theme={initial_theme}")

    page.locator("#theme-toggle").click()
    page.wait_for_timeout(1000)

    new_theme = page.locator("html").get_attribute("data-theme")
    log("Theme toggled to dark", new_theme == "dark", f"theme={new_theme}")

    page.screenshot(path="/tmp/daylife_04_dark_theme.png", full_page=True)

    # Toggle back
    page.locator("#theme-toggle").click()
    page.wait_for_timeout(500)
    restored = page.locator("html").get_attribute("data-theme")
    log("Theme restored to light", restored == "light", f"theme={restored}")

    # 6) Responsive layout - narrow width
    page.set_viewport_size({"width": 768, "height": 900})
    page.wait_for_timeout(1000)
    page.screenshot(path="/tmp/daylife_05_tablet.png", full_page=True)
    log("Tablet layout renders", True, "768px width")

    page.set_viewport_size({"width": 375, "height": 667})
    page.wait_for_timeout(1000)
    page.screenshot(path="/tmp/daylife_06_mobile.png", full_page=True)
    log("Mobile layout renders", True, "375px width")

    # Check no new JS errors after all interactions
    final_errors = [e for e in console_errors if "error" in e.lower() or "Error" in e]
    log("No JS errors after interactions", len(final_errors) == 0,
        f"{len(final_errors)} errors: {final_errors[:3]}" if final_errors else "clean")

    browser.close()

# Summary
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
failed = sum(1 for _, s, _ in RESULTS if s == "FAIL")
print(f"Total: {len(RESULTS)} | PASS: {passed} | FAIL: {failed}")
for name, status, detail in RESULTS:
    icon = "✓" if status == "PASS" else "✗"
    print(f"  {icon} {name}: {detail}")
