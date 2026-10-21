def test_create_bid(client, make_client):
    acme = make_client()
    response = client.post(
        "/bids",
        json={
            "client_id": acme["id"],
            "title": "Website",
            "value": 100000,
            "estimated_cost": 80000,
            "deadline": "2026-12-01",
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "draft"


def test_create_bid_unknown_client_returns_404(client):
    response = client.post(
        "/bids",
        json={
            "client_id": 999,
            "title": "Website",
            "value": 100000,
            "estimated_cost": 80000,
            "deadline": "2026-12-01",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_create_bid_negative_value_returns_422(client, make_client):
    acme = make_client()
    response = client.post(
        "/bids",
        json={
            "client_id": acme["id"],
            "title": "Website",
            "value": -5,
            "estimated_cost": 80000,
            "deadline": "2026-12-01",
        },
    )
    assert response.status_code == 422
    assert response.json()["details"][0]["field"] == "body.value"


def test_get_bid(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    response = client.get(f"/bids/{bid['id']}")
    assert response.status_code == 200
    assert response.json()["title"] == "Website redesign"


def test_get_missing_bid_returns_404(client):
    response = client.get("/bids/999")
    assert response.status_code == 404
    assert response.json()["message"] == "Bid 999 not found"


def test_list_bids_with_filters(client, make_client, make_bid):
    acme = make_client("Acme Corp")
    globex = make_client("Globex")
    make_bid(acme["id"], title="A", status="submitted")
    make_bid(acme["id"], title="B")
    make_bid(globex["id"], title="C")

    assert len(client.get("/bids").json()) == 3
    assert [b["title"] for b in client.get("/bids?status=submitted").json()] == ["A"]
    assert [b["title"] for b in client.get(f"/bids?client_id={globex['id']}").json()] == ["C"]
    both = client.get(f"/bids?client_id={acme['id']}&status=draft").json()
    assert [b["title"] for b in both] == ["B"]


def test_list_bids_invalid_status_returns_422(client):
    assert client.get("/bids?status=bogus").status_code == 422


def test_update_bid_changes_only_sent_fields(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    response = client.put(f"/bids/{bid['id']}", json={"status": "submitted", "value": 110000})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "submitted"
    assert data["value"] == 110000
    assert data["title"] == "Website redesign"  # untouched
    assert client.get(f"/bids/{bid['id']}").json()["status"] == "submitted"  # saved


def test_update_missing_bid_returns_404(client):
    response = client.put("/bids/999", json={"notes": "x"})
    assert response.status_code == 404


def test_update_bid_with_null_title_returns_422(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    response = client.put(f"/bids/{bid['id']}", json={"title": None})
    assert response.status_code == 422


def test_delete_bid(client, make_client, make_bid):
    bid = make_bid(make_client()["id"])
    assert client.delete(f"/bids/{bid['id']}").status_code == 204
    assert client.get(f"/bids/{bid['id']}").status_code == 404


def test_delete_missing_bid_returns_404(client):
    assert client.delete("/bids/999").status_code == 404