from app.config import settings

HEADER = "client_name,industry,past_bids_won,past_bids_lost,title,value,estimated_cost,deadline,status,notes\n"


def write_csv(tmp_path, monkeypatch, rows):
    path = tmp_path / "bids.csv"
    path.write_text(HEADER + "\n".join(rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(settings, "bids_csv_path", str(path))


def test_import_creates_bids_and_skips_duplicates_on_second_run(client, tmp_path, monkeypatch):
    write_csv(
        tmp_path,
        monkeypatch,
        [
            "Acme Corp,Retail,6,1,Website,100000,72000,2026-12-15,draft,",
            "Initech,Technology,5,0,API gateway,90000,65000,2026-12-01,won,",
        ],
    )
    assert client.post("/import/bids").json() == {"created": 2, "duplicates": 0, "errors": []}
    assert client.post("/import/bids").json() == {"created": 0, "duplicates": 2, "errors": []}
    assert len(client.get("/bids").json()) == 2


def test_import_reports_bad_rows(client, tmp_path, monkeypatch):
    write_csv(
        tmp_path,
        monkeypatch,
        [
            "Acme Corp,Retail,6,1,Good bid,100000,72000,2026-12-15,draft,",
            "Acme Corp,Retail,6,1,Bad value,-100,50,2026-12-01,draft,",
            "Acme Corp,Retail,6,1,Bad date,1000,500,not-a-date,draft,",
        ],
    )
    result = client.post("/import/bids").json()
    assert result["created"] == 1
    assert len(result["errors"]) == 2
    assert result["errors"][0].startswith("line 3")
    assert result["errors"][1].startswith("line 4")


def test_import_missing_file_returns_clear_error(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "bids_csv_path", str(tmp_path / "missing.csv"))
    response = client.post("/import/bids")
    assert response.status_code == 500
    assert response.json()["error"] == "import_file_error"