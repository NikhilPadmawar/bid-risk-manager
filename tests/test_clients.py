def test_create_client(client):
    response = client.post("/clients", json={"name": "Acme Corp", "industry": "Retail"})
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Acme Corp"
    assert data["past_bids_won"] == 0


def test_duplicate_client_returns_409(client, make_client):
    make_client("Acme Corp")
    response = client.post("/clients", json={"name": "Acme Corp"})
    assert response.status_code == 409
    assert response.json()["error"] == "conflict"


def test_client_with_empty_name_returns_422(client):
    response = client.post("/clients", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"