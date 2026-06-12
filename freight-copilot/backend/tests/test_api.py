"""End-to-end API/workflow smoke tests via FastAPI TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client():
    from app.main import create_app

    return TestClient(create_app())


def test_health_and_flags():
    with _client() as c:
        assert c.get("/api/health").json() == {"status": "ok"}
        flags = c.get("/api/flags").json()
        assert flags["EXTERNAL_WRITES_ENABLED"] is False
        assert flags["DEMO_MODE"] is True


def test_demo_data_seeded_and_listed():
    with _client() as c:
        offers = c.get("/api/offers").json()
        assert len(offers) >= 20
        carriers = c.get("/api/carriers").json()
        assert len(carriers) >= 15


def test_workflow_a_intake_normalizes_and_scores():
    with _client() as c:
        r = c.post(
            "/api/intake",
            json={
                "text": "Carico Warsaw (PL) -> Milan (IT), 22t tautliner, ADR, 12/06, 1850 EUR",
                "source": "manual",
            },
        )
        body = r.json()
        assert body["score"] is not None
        assert body["priority"]


def test_workflow_b_offer_detail_returns_carriers_with_risk():
    with _client() as c:
        offer_id = c.get("/api/offers").json()[0]["id"]
        detail = c.get(f"/api/offers/{offer_id}").json()
        assert "carriers" in detail
        assert detail["analysis"]["pricing"]["output"]["margin_pct"] is not None


def test_workflow_c_shipments_have_alerts():
    with _client() as c:
        ships = c.get("/api/shipments").json()
        assert any(s["alerts"] for s in ships)  # problematic shipments produce alerts


def test_approval_is_simulated_in_demo_mode():
    with _client() as c:
        ap = c.get("/api/approvals").json()[0]
        out = c.post(f"/api/approvals/{ap['id']}/decision", params={"decision": "approved"}).json()
        assert out["state"] == "simulated"  # never a real external write in demo


def test_knowledge_crud_and_search():
    with _client() as c:
        created = c.post("/api/knowledge", json={"title": "Test lane", "body": "PL-IT note"}).json()
        nid = created["id"]
        found = c.get("/api/knowledge", params={"q": "PL-IT"}).json()
        assert any(n["id"] == nid for n in found)
        assert c.delete(f"/api/knowledge/{nid}").json()["deleted"] == nid


def test_pages_render():
    with _client() as c:
        for path in [
            "/",
            "/opportunities",
            "/carriers",
            "/transports",
            "/approvals",
            "/documents",
            "/knowledge",
            "/settings",
        ]:
            assert c.get(path).status_code == 200
