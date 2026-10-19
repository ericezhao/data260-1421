"""Exercise the MongoDB document API and print one result per call."""

from datetime import datetime

import httpx

BASE = "http://127.0.0.1:8521"


def show(title: str, response: httpx.Response) -> None:
    body = response.text.strip()
    if len(body) > 500:
        body = body[:500] + "..."
    print(f"\n{title}")
    print(f"status {response.status_code}")
    print(body)


def main() -> None:
    print("Eric Zhao (SID4 1421)")
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with httpx.Client(base_url=BASE, timeout=20) as client:
        show("GET /api/documents", client.get("/api/documents"))
        created = client.post("/api/documents", json={
            "restaurantName": "Homework Grill",
            "notes": "Created from run_hw06_part1.py",
            "cuisine": "American",
            "inspectedAt": "2026-10-18T16:00:00Z",
            "score": 95,
            "violations": [{"description": "No soap at the hand sink", "severity": "major"}],
        })
        show("POST /api/documents", created)
        doc_id = created.json()["id"]
        show("GET /api/documents/{id}", client.get(f"/api/documents/{doc_id}"))
        show("PUT /api/documents/{id}", client.put(
            f"/api/documents/{doc_id}", json={"status": "follow_up", "score": 90}
        ))
        show("POST missing cuisine", client.post("/api/documents", json={
            "restaurantName": "No Cuisine",
            "inspectedAt": "2026-10-18T16:00:00Z",
        }))
        show("POST bad cuisine", client.post("/api/documents", json={
            "restaurantName": "Bad Cuisine",
            "cuisine": "Martian",
            "inspectedAt": "2026-10-18T16:00:00Z",
        }))
        show("POST bad json", client.post(
            "/api/documents",
            content='{"restaurantName": ',
            headers={"Content-Type": "application/json"},
        ))
        show("GET bad id", client.get("/api/documents/not-an-id"))
        show("DELETE /api/documents/{id}", client.delete(f"/api/documents/{doc_id}"))
        show("GET deleted id", client.get(f"/api/documents/{doc_id}"))


if __name__ == "__main__":
    main()
