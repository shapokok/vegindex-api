import pytest
from fastapi.testclient import TestClient

from vegindex import __version__
from vegindex.api import MAX_CSV_BYTES, app
from vegindex.schemas import MAX_OBSERVATIONS


@pytest.fixture
def client():
    return TestClient(app)


def upload(client, content: bytes | str, filename: str = "pixels.csv"):
    if isinstance(content, str):
        content = content.encode()
    return client.post("/indices/csv", files={"file": (filename, content, "text/csv")})


# --- service endpoints ---------------------------------------------------------


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version(client, monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "abc1234")
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"name": "vegindex-api", "version": __version__, "commit": "abc1234"}


def test_version_without_commit(client, monkeypatch):
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert client.get("/version").json()["commit"] == "unknown"


# --- POST /indices ------------------------------------------------------------


def test_indices_full_pixel(client):
    response = client.post(
        "/indices", json=[{"id": "p1", "red": 20, "green": 50, "blue": 30, "nir": 80}]
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    result = body["results"][0]
    assert result["id"] == "p1"
    assert result["ndvi"] == pytest.approx(0.6)  # (80-20)/(80+20)
    assert result["ndvi_class"] == "healthy"
    assert result["vari"] == pytest.approx(0.75)  # (50-20)/(50+20-30)
    assert result["exg"] == pytest.approx(0.5)


def test_indices_nir_only_observation(client):
    response = client.post("/indices", json=[{"red": 0.3, "nir": 0.45}])
    result = response.json()["results"][0]
    assert result["ndvi"] == pytest.approx(0.2)
    assert result["ndvi_class"] == "stressed"
    assert result["vari"] is None
    assert result["exg"] is None


def test_indices_rgb_only_pixel(client):
    response = client.post("/indices", json=[{"red": 0.3, "green": 0.5, "blue": 0.2}])
    result = response.json()["results"][0]
    assert result["ndvi"] is None
    assert result["ndvi_class"] is None
    assert result["vari"] == pytest.approx(1 / 3)


def test_indices_preserves_order_for_mixed_batch(client):
    payload = [
        {"id": "water", "red": 0.3, "nir": 0.1},
        {"id": "rgb", "red": 0.3, "green": 0.5, "blue": 0.2},
        {"id": "dark", "red": 0, "green": 0, "blue": 0, "nir": 0},
    ]
    results = client.post("/indices", json=payload).json()["results"]
    assert [r["id"] for r in results] == ["water", "rgb", "dark"]
    assert results[0]["ndvi_class"] == "no vegetation"
    assert results[2] == {
        "id": "dark",
        "ndvi": 0.0,
        "ndvi_class": "no vegetation",
        "vari": 0.0,
        "exg": 0.0,
    }


def test_indices_empty_list(client):
    response = client.post("/indices", json=[])
    assert response.status_code == 200
    assert response.json() == {"count": 0, "results": []}


@pytest.mark.parametrize(
    "item",
    [
        {"red": -0.1, "nir": 0.5},  # negative reflectance
        {"red": 0.1},  # not enough bands
        {"red": 0.1, "green": 0.2},  # blue missing, no nir
        {"nir": 0.5},  # red missing
        {"red": "abc", "nir": 0.5},  # not a number
        {"red": 0.1, "nir": 0.5, "swir": 0.3},  # unknown field
    ],
)
def test_indices_rejects_invalid_items(client, item):
    assert client.post("/indices", json=[item]).status_code == 422


def test_indices_rejects_non_list_body(client):
    assert client.post("/indices", json={"red": 0.1, "nir": 0.5}).status_code == 422


def test_indices_rejects_too_many_items(client):
    payload = [{"red": 0.1, "nir": 0.5}] * (MAX_OBSERVATIONS + 1)
    assert client.post("/indices", json=payload).status_code == 422


# --- POST /indices/csv --------------------------------------------------------


def test_csv_upload(client):
    csv_text = "id,red,green,blue,nir\np1,20,50,30,80\np2,0.3,,,0.45\n"
    response = upload(client, csv_text)
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert body["results"][0]["ndvi"] == pytest.approx(0.6)
    assert body["results"][1]["ndvi_class"] == "stressed"
    assert body["results"][1]["vari"] is None


def test_csv_headers_are_case_insensitive_and_bom_is_ignored(client):
    csv_bytes = "﻿Red, NIR ,Comment\n0.2,0.8,field A\n".encode()
    response = upload(client, csv_bytes)
    assert response.status_code == 200
    assert response.json()["results"][0]["ndvi"] == pytest.approx(0.6)


def test_csv_skips_blank_lines(client):
    response = upload(client, "red,nir\n0.2,0.8\n\n,\n0.3,0.1\n")
    assert response.json()["count"] == 2


def test_csv_missing_red_column(client):
    response = upload(client, "nir,green\n0.8,0.5\n")
    assert response.status_code == 422
    assert "red" in response.json()["detail"]


def test_csv_invalid_value_reports_line(client):
    response = upload(client, "red,nir\n0.2,0.8\n0.3,oops\n")
    assert response.status_code == 422
    assert response.json()["detail"].startswith("line 3:")


def test_csv_empty_file(client):
    response = upload(client, "")
    assert response.status_code == 422
    assert response.json()["detail"] == "CSV file is empty"


def test_csv_non_utf8(client):
    response = upload(client, "red,nir\n0,2;0,8\n".encode("utf-16"))
    assert response.status_code == 422


def test_csv_too_large(client):
    response = upload(client, b"red,nir\n" + b"0.2,0.8\n" * (MAX_CSV_BYTES // 8 + 1))
    assert response.status_code == 413


def test_csv_requires_file(client):
    assert client.post("/indices/csv").status_code == 422
