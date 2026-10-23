from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from v4.reservation_service.app.db import get_db
from v4.reservation_service.app.main import app


client = TestClient(app)


def make_reservation(
    username: str = "test_user",
    status: str = "RENTED",
    till_date: date | None = None,
    book_uid=None,
    library_uid=None,
    reservation_uid=None,
):
    reservation = MagicMock()
    reservation.reservation_uid = reservation_uid or uuid4()
    reservation.username = username
    reservation.book_uid = book_uid or uuid4()
    reservation.library_uid = library_uid or uuid4()
    reservation.status = status
    reservation.start_date = date(2026, 9, 21)
    reservation.till_date = till_date or date(2026, 9, 28)
    return reservation

def test_get_reservations():
    reservation = make_reservation()

    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [reservation]

    app.dependency_overrides[get_db] = lambda: db

    response = client.get(
        "/api/v1/reservations",
        headers={"X-User-Name": "test_user"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["reservationUid"] == str(reservation.reservation_uid)
    assert data[0]["bookUid"] == str(reservation.book_uid)
    assert data[0]["libraryUid"] == str(reservation.library_uid)
    assert data[0]["status"] == "RENTED"


def test_get_reservations_empty():
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []

    app.dependency_overrides[get_db] = lambda: db

    response = client.get(
        "/api/v1/reservations",
        headers={"X-User-Name": "test_user"},
    )

    assert response.status_code == 200
    assert response.json() == []


def test_create_reservation():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db

    book_uid = uuid4()
    library_uid = uuid4()

    response = client.post(
        "/api/v1/reservations",
        headers={"X-User-Name": "test_user"},
        json={
            "bookUid": str(book_uid),
            "libraryUid": str(library_uid),
            "tillDate": "2030-09-28",
        },
    )

    assert response.status_code == 200

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

    data = response.json()
    assert data["bookUid"] == str(book_uid)
    assert data["libraryUid"] == str(library_uid)
    assert data["status"] == "RENTED"

def test_create_reservation_invalid_body():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db

    response = client.post(
        "/api/v1/reservations",
        headers={"X-User-Name": "test_user"},
        json={"bookUid": "not-a-uuid"},
    )

    assert response.status_code == 422
    db.add.assert_not_called()

def test_get_reservation_by_uid():
    reservation = make_reservation()

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = reservation

    app.dependency_overrides[get_db] = lambda: db

    response = client.get(
        f"/api/v1/reservations/{reservation.reservation_uid}",
        headers={"X-User-Name": "test_user"},
    )

    assert response.status_code == 200
    assert response.json()["reservationUid"] == str(reservation.reservation_uid)


def test_get_reservation_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = lambda: db

    response = client.get(
        f"/api/v1/reservations/{uuid4()}",
        headers={"X-User-Name": "test_user"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"

def test_return_reservation_on_time():
    reservation = make_reservation(
        till_date=date(2026, 9, 28),
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = reservation

    app.dependency_overrides[get_db] = lambda: db

    response = client.post(
        f"/api/v1/reservations/{reservation.reservation_uid}/return",
        headers={"X-User-Name": "test_user"},
        json={
            "condition": "EXCELLENT",
            "date": "2026-09-28",
        },
    )

    assert response.status_code == 204
    assert reservation.status == "RETURNED"
    db.commit.assert_called_once()


def test_return_reservation_expired():
    reservation = make_reservation(till_date=date(2026, 9, 28))

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = reservation

    app.dependency_overrides[get_db] = lambda: db

    response = client.post(
        f"/api/v1/reservations/{reservation.reservation_uid}/return",
        headers={"X-User-Name": "test_user"},
        json={
            "condition": "EXCELLENT",
            "date": "2026-09-29",
        },
    )

    assert response.status_code == 204
    assert reservation.status == "EXPIRED"
    db.commit.assert_called_once()


def test_return_reservation_not_found():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_db] = lambda: db

    response = client.post(
        f"/api/v1/reservations/{uuid4()}/return",
        headers={"X-User-Name": "test_user"},
        json={
            "condition": "EXCELLENT",
            "date": "2026-09-28",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Reservation not found"


def test_return_reservation_already_returned():
    reservation = make_reservation(
        status="RETURNED",
        till_date=date(2026, 9, 28),
    )

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = reservation

    app.dependency_overrides[get_db] = lambda: db

    response = client.post(
        f"/api/v1/reservations/{reservation.reservation_uid}/return",
        headers={"X-User-Name": "test_user"},
        json={
            "condition": "EXCELLENT",
            "date": "2026-09-28",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Reservation is not active"
    db.commit.assert_not_called()
