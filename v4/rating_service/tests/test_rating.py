from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from v4.rating_service.app.db import get_db
from v4.rating_service.app.main import app

client = TestClient(app)


def test_get_rating():
    rating = MagicMock()
    rating.username = "test_user"
    rating.stars = 75

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = rating

    app.dependency_overrides[get_db] = lambda: db

    response = client.get("/api/v1/rating", headers={"X-User-Name": "test_user"})

    assert response.status_code == 200
    assert response.json() == {"stars": 75}

    db.query.assert_called_once()


def test_get_rating_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = lambda: db

    response = client.get("/api/v1/rating", headers={"X-User-Name": "unknown_user"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Rating not found"

def test_update_rating():
    rating = MagicMock()
    rating.username = "test_user"
    rating.stars = 50

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = rating

    app.dependency_overrides[get_db] = lambda: db

    response = client.patch(
        "/api/v1/rating",
        headers={"X-User-Name": "test_user"},
        json={"stars": 75},
    )

    assert response.status_code == 200
    assert response.json() == {"stars": 75}
    assert rating.stars == 75

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(rating)


def test_update_rating_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = lambda: db

    response = client.patch(
        "/api/v1/rating",
        headers={"X-User-Name": "unknown_user"},
        json={"stars": 50},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Rating not found"

    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_update_rating_clamps_to_min():
    rating = MagicMock()
    rating.username = "test_user"
    rating.stars = 50

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = rating

    app.dependency_overrides[get_db] = lambda: db

    response = client.patch(
        "/api/v1/rating",
        headers={"X-User-Name": "test_user"},
        json={"stars": 0},
    )

    assert response.status_code == 200
    assert response.json() == {"stars": 1}
    assert rating.stars == 1


def test_update_rating_clamps_to_max():
    rating = MagicMock()
    rating.username = "test_user"
    rating.stars = 50

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = rating

    app.dependency_overrides[get_db] = lambda: db

    response = client.patch(
        "/api/v1/rating",
        headers={"X-User-Name": "test_user"},
        json={"stars": 1000},
    )

    assert response.status_code == 200
    assert response.json() == {"stars": 100}
    assert rating.stars == 100
