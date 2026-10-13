"""Real browser -> Next.js -> FastAPI -> real models -> isolated SQLite fixture."""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from backend.src.models.orm import UserEvent
from scripts.report_recommendation_ab import report

output = ROOT / "training/evaluation/results/ab_browser_smoke_20261012"
output.mkdir(parents=True, exist_ok=True)
checks = {}

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    # Only external image acquisition is replaced. Catalog metadata and models are real fixtures/checkpoints.
    page.route("**/api/products/*/images*", lambda route: route.fulfill(json={"images": []}))
    feeds = []
    page.on("response", lambda response: feeds.append(response.json()) if "/api/recommendations?" in response.url and response.status == 200 else None)
    page.goto("http://127.0.0.1:13000", wait_until="domcontentloaded")
    cards = page.locator(".recommendation-strip-section [data-rec-index]")
    cards.first.wait_for(timeout=60000)
    initial_count = cards.count()
    assert initial_count >= 1
    section = page.locator(".recommendation-strip-section")
    assert section.get_by_role("button", name="Xem thêm sản phẩm gợi ý").count() == 0
    # Force one recoverable pagination failure and confirm old cards remain.
    failures = {"count": 0}
    def fail_once(route):
        if "cursor=" in route.request.url and failures["count"] == 0:
            failures["count"] += 1
            route.fulfill(status=503, json={"error": "Tạm thời chưa tải được gợi ý", "items": []})
        else:
            route.continue_()
    page.route("**/api/recommendations?**", fail_once)
    section.scroll_into_view_if_needed()
    page.wait_for_timeout(1400)
    page.locator(".rec-load-sentinel").scroll_into_view_if_needed()
    section.get_by_role("button", name="Thử lại").wait_for(timeout=15000)
    assert cards.count() == initial_count
    section.get_by_role("button", name="Thử lại").click()
    section.get_by_role("status", name="Đang tải gợi ý", exact=True).wait_for(timeout=5000)
    assert cards.count() == initial_count
    checks["loading_shown_before_appending_products"] = True
    page.wait_for_function("document.querySelectorAll('[data-rec-index]').length > " + str(initial_count), timeout=20000)
    checks["scroll_appends_without_manual_load_button"] = True
    checks["pagination_failure_preserves_cards_and_retry_recovers"] = True
    hrefs = cards.locator(".product-info a").evaluate_all("nodes => nodes.map(node => node.getAttribute('href'))")
    assert len(hrefs) == len(set(hrefs))
    checks["no_duplicate_products"] = True
    assert feeds[1]["request_id"] == feeds[0]["request_id"]
    checks["same_persisted_snapshot_across_pages"] = True
    settled_count = cards.count()
    page.wait_for_timeout(1200)
    assert cards.count() == settled_count
    checks["standing_still_does_not_load_multiple_pages"] = True
    page.locator(".rec-load-sentinel").scroll_into_view_if_needed()
    page.wait_for_function("document.querySelectorAll('[data-rec-index]').length > 24", timeout=60000)
    assert len({feed["request_id"] for feed in feeds}) > 1
    assert all(feed["experiment"] == feeds[0]["experiment"] for feed in feeds)
    hrefs = cards.locator(".product-info a").evaluate_all("nodes => nodes.map(node => node.getAttribute('href'))")
    assert len(hrefs) == len(set(hrefs))
    checks["scroll_retrieves_new_block_same_group_no_repeats"] = True
    page.screenshot(path=str(output / "desktop.png"), full_page=True)
    # A like button is not counted as a recommendation link click.
    page.locator("[data-rec-index='0']").scroll_into_view_if_needed()
    page.wait_for_timeout(1200)
    page.wait_for_function("!localStorage.getItem('merrec_interactions:guest') || JSON.parse(localStorage.getItem('merrec_interactions:guest')).length===0", timeout=15000)
    engine = create_engine("sqlite:///" + str(output / "fixture.sqlite"))
    with Session(engine) as db:
        before_clicks = db.query(UserEvent).filter_by(event_type="click").count()
    page.locator("[data-rec-index='0'] .wishlist-btn").click()
    page.wait_for_timeout(600)
    with Session(engine) as db:
        assert db.query(UserEvent).filter_by(event_type="click").count() == before_clicks
    with page.expect_navigation(wait_until="domcontentloaded"):
        page.locator("[data-rec-index='0'] .product-info a").click()
    page.wait_for_timeout(1000)
    with Session(engine) as db:
        assert db.query(UserEvent).filter_by(event_type="click").count() > before_clicks
        result = report(db, feeds[0]["experiment"]["id"])
        assert sum(group["impressions"] for group in result["groups"].values()) > 0
        assert sum(group["clicked_impressions"] for group in result["groups"].values()) > 0
    checks["browser_impressions_clicks_persist_and_report"] = True
    checks["like_is_not_miscounted_as_click"] = True
    original_group = feeds[0]["experiment"]
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto("http://127.0.0.1:13000", wait_until="domcontentloaded")
    cards.first.wait_for(timeout=60000)
    assert feeds[-1]["experiment"] == original_group
    checks["group_survives_reload"] = True
    section.scroll_into_view_if_needed()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.screenshot(path=str(output / "mobile.png"), full_page=True)
    checks["mobile_390px_no_horizontal_overflow"] = True
    assert not errors, errors
    checks["no_browser_javascript_errors"] = True
    # Reproduce the real regression: a queued view fails to sync, but the
    # anonymous homepage must still render. Restore the boundary and verify
    # the original event is durable after retry, not silently acknowledged.
    recovery_context = browser.new_context(viewport={"width": 1440, "height": 1000})
    recovery = recovery_context.new_page()
    session_id, event_key = str(uuid.uuid4()), str(uuid.uuid4())
    recovery.add_init_script("""(() => {
      if (!localStorage.getItem('queue_recovery_initialized')) {
        localStorage.setItem('queue_recovery_initialized', '1');
        sessionStorage.setItem('merrec_recommendation_session', JSON.stringify({id: %s, userId:'guest', updatedAt:Date.now()}));
        localStorage.setItem('merrec_interactions:guest', JSON.stringify([{item_id:'2',event_type:'view',session_id:%s,event_key:%s}]));
      }
    })();""" % (json.dumps(session_id), json.dumps(session_id), json.dumps(event_key)))
    recovery.route("**/api/products/*/images*", lambda route: route.fulfill(json={"images": []}))
    recovery.route("**/api/events", lambda route: route.fulfill(status=503, json={"error": "Test dependency unavailable"}))
    recovery.goto("http://127.0.0.1:13000", wait_until="domcontentloaded")
    recovery.locator("[data-rec-index]").first.wait_for(timeout=60000)
    assert recovery.evaluate("JSON.parse(localStorage.getItem('merrec_interactions:guest')).some(event => event.event_type==='view')")
    assert recovery.get_by_text("Tương tác chưa được lưu. Vui lòng thử đồng bộ trước khi tải gợi ý mới.", exact=True).count() == 0
    checks["event_outage_does_not_block_guest_recommendations"] = True
    recovery.unroute("**/api/events")
    recovery.evaluate("window.dispatchEvent(new Event('online'))")
    recovery.wait_for_function("JSON.parse(localStorage.getItem('merrec_interactions:guest') || '[]').length===0", timeout=20000)
    with Session(engine) as db:
        saved = db.query(UserEvent).filter_by(event_key=event_key).one()
        assert saved.event_type == "view" and saved.item_id == "2"
    checks["failed_view_survives_and_persists_after_dependency_recovers"] = True
    recovery_context.close()
    browser.close()
    engine.dispose()

(output / "checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
print(json.dumps(checks, indent=2))
