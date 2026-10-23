import os
import time
from uuid import UUID
from datetime import date
from collections import deque
from threading import Thread, Lock
import httpx
from fastapi import FastAPI, Response, Query, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI(title="Gateway Service")

LIBRARY_SERVICE_URL = os.getenv("LIBRARY_SERVICE_URL", "http://library-service:8060")
RESERVATION_SERVICE_URL = os.getenv("RESERVATION_SERVICE_URL", "http://reservation-service:8070")
RATING_SERVICE_URL = os.getenv("RATING_SERVICE_URL", "http://rating-service:8050")

retry_queue = deque()
queue_lock = Lock()

class ReservationRequest(BaseModel):
    bookUid: UUID
    libraryUid: UUID
    tillDate: date

class ReturnRequest(BaseModel):
    condition: str
    date: date


def to_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])

@app.get("/manage/health")
def health():
    return {"status": "UP"}

def enqueue(operation: dict):
    with queue_lock:
        retry_queue.append(operation)

def send_request(method: str, url: str, headers: dict | None = None, params: dict | None = None, json: dict | None = None, timeout: float = 2.0):
    try:
        return httpx.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json,
            timeout=timeout,
        )
    except httpx.RequestError:
        return None

def retry_request(method: str, url: str, headers: dict | None = None, params: dict | None = None, json: dict | None = None, timeout: int = 10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = send_request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json,
            timeout=2.0,
        )

        if response is not None:
            if response.status_code < 500:
                return response

        time.sleep(1)

    return None

def update_rating(username: str, delta: int) -> bool:
    headers = {"X-User-Name": username}

    response = send_request("GET", f"{RATING_SERVICE_URL}/api/v1/rating", headers=headers)

    if response is None or response.status_code != 200:
        return False

    try:
        stars = response.json()["stars"]
    except (ValueError, KeyError, TypeError):
        return False

    new_stars = max(1, min(100, stars + delta))

    response = send_request(
        "PATCH",
        f"{RATING_SERVICE_URL}/api/v1/rating",
        headers=headers,
        json={"stars": new_stars},
    )

    return response is not None and response.status_code in (200, 204)

def process_operation(operation: dict) -> bool:
    if operation["type"] == "rating":
        return update_rating(operation["username"], operation["delta"])

    response = send_request(
        operation["method"],
        operation["url"],
        headers=operation.get("headers"),
        json=operation.get("json"),
    )

    return response is not None and response.status_code in (200, 204)

def process_pending_for_user(username: str):
    with queue_lock:
        pending = [
            operation for operation in retry_queue
            if operation.get("username") == username
        ]

    for operation in pending:
        if process_operation(operation):
            with queue_lock:
                try:
                    retry_queue.remove(operation)
                except ValueError:
                    pass

def queue_worker():
    while True:
        with queue_lock:
            operation = retry_queue[0] if retry_queue else None

        if operation is not None and process_operation(operation):
            with queue_lock:
                try:
                    retry_queue.remove(operation)
                except ValueError:
                    pass

        time.sleep(1)

def retry_rating_update(username: str, delta: int, timeout: int = 10) -> bool:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if update_rating(username, delta):
            return True

        time.sleep(1)

    return False

@app.on_event("startup")
def start_queue_worker():
    Thread(target=queue_worker, daemon=True).start()

def proxy_request(method: str, url: str, params: dict | None = None, headers: dict | None = None, json: dict | None = None, error_message: str = "Upstream service is unavailable",):
    try:
        response = httpx.request(method=method, url=url, params=params, headers=headers, json=json, timeout=5.0)
    except httpx.RequestError:
       return JSONResponse(status_code=503, content={"message": error_message})

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={"content-type": response.headers.get("content-type", "application/json")},
    )

def proxy_get(url: str, params: dict | None = None, headers: dict | None = None, error_message: str = "Upstream service is unavailable",):
    try:
        response = httpx.get(
            url,
            params=params,
            headers=headers,
            timeout=5.0,
        )
    except httpx.RequestError:
        return JSONResponse(
            status_code=503,
            content={"message": error_message},
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers={
            "content-type": response.headers.get(
                "content-type", "application/json"
            )
        },
    )


# ---------------- LIBRARY SERVICE ----------------

def get_library_info(library_uid) -> dict:
    try:
        response = httpx.get(
            f"{LIBRARY_SERVICE_URL}/api/v1/libraries/{library_uid}",
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Library Service is unavailable")

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Unable to get library")

    return response.json()


def get_book_info(library_uid, book_uid) -> dict:
    try:
        response = httpx.get(
            f"{LIBRARY_SERVICE_URL}/api/v1/libraries/{library_uid}/books",
            params={
                "page": 1,
                "size": 100,
                "showAll": True,
            },
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Library Service is unavailable")

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Unable to get library books")

    book = next(
        (item for item in response.json()["items"] if item["bookUid"] == str(book_uid)),
        None,
    )

    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    return book


def enrich_reservation(reservation: dict, book: dict, library: dict) -> dict:
    return {
        "reservationUid": str(reservation["reservationUid"]),
        "status": reservation["status"],
        "startDate": to_date(reservation["startDate"]).isoformat(),
        "tillDate": to_date(reservation["tillDate"]).isoformat(),
        "book": {
            "bookUid": book["bookUid"],
            "name": book["name"],
            "author": book["author"],
            "genre": book["genre"],
        },
        "library": {
            "libraryUid": library["libraryUid"],
            "name": library["name"],
            "address": library["address"],
            "city": library["city"],
        },
    }


@app.get("/api/v1/libraries")
def get_libraries(city: str, page: int = Query(0, ge=0), size: int = Query(10, ge=1)):
    return proxy_get(
        f"{LIBRARY_SERVICE_URL}/api/v1/libraries",
        params={
            "city": city,
            "page": page,
            "size": size,
        },
    )


# @app.get("/api/v1/libraries/{library_uid}")
# def get_library(library_uid: UUID):
#     return proxy_get(
#         f"{LIBRARY_SERVICE_URL}/api/v1/libraries/{library_uid}",
#     )


# GET /api/v1/libraries/{library_uid}/books?page=0&size=10&showAll=false
@app.get("/api/v1/libraries/{library_uid}/books")
def get_books(library_uid: UUID, page: int = Query(0, ge=0), size: int = Query(10, ge=1), showAll: bool = False):
    return proxy_get(
        f"{LIBRARY_SERVICE_URL}/api/v1/libraries/{library_uid}/books",
        params={
            "page": page,
            "size": size,
            "showAll": showAll,
        },
    )

# ---------------- RESERVATION SERVICE ----------------

@app.get("/api/v1/reservations")
def get_reservations(x_user_name: str = Header(..., alias="X-User-Name")):
    try:
        response = httpx.get(
            f"{RESERVATION_SERVICE_URL}/api/v1/reservations",
            headers={"X-User-Name": x_user_name},
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Reservation Service is unavailable")

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Unable to get user reservations")

    libraries: dict[str, dict] = {}
    books: dict[tuple[str, str], dict] = {}
    reservations = []

    for reservation in response.json():
        library_uid = str(reservation["libraryUid"])
        book_uid = str(reservation["bookUid"])

        try:
            if library_uid not in libraries:
                libraries[library_uid] = get_library_info(library_uid)

            if (library_uid, book_uid) not in books:
                books[(library_uid, book_uid)] = get_book_info(
                    library_uid, book_uid
                )

            reservations.append(
                enrich_reservation(
                    reservation,
                    books[(library_uid, book_uid)],
                    libraries[library_uid],
                )
            )
        except HTTPException as exc:
            if exc.status_code not in (502, 503, 504):
                raise

            reservations.append({
                "reservationUid": str(reservation["reservationUid"]),
                "status": reservation["status"],
                "startDate": to_date(reservation["startDate"]).isoformat(),
                "tillDate": to_date(reservation["tillDate"]).isoformat(),
                "book": {"bookUid": book_uid},
                "library": {"libraryUid": library_uid},
            })
        
    return JSONResponse(content=reservations, status_code=200)

@app.post("/api/v1/reservations")
def create_reservation(body: ReservationRequest, x_user_name: str = Header(..., alias="X-User-Name")):
    headers = {"X-User-Name": x_user_name}

    try:
        rating_response = httpx.get(
            f"{RATING_SERVICE_URL}/api/v1/rating",
            headers=headers,
            timeout=5.0,
        )
    except httpx.RequestError:
        return JSONResponse(status_code=503, content={"message": "Bonus Service unavailable"},)

    if rating_response.status_code != 200:
        return JSONResponse(status_code=rating_response.status_code, content={"message": "Bonus Service unavailable"},)

    rating_data = rating_response.json()
    stars = rating_data["stars"]
    
    try:
        reservations_response = httpx.get(
            f"{RESERVATION_SERVICE_URL}/api/v1/reservations",
            headers=headers,
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Reservation Service is unavailable")

    if reservations_response.status_code != 200:
        raise HTTPException(status_code=reservations_response.status_code, detail="Unable to get user reservations")

    reservations = reservations_response.json()

    active_reservations = [
        reservation
        for reservation in reservations
        if reservation.get("status") == "RENTED"
    ]
    active_count = len(active_reservations)
    if active_count >= stars:
        raise HTTPException(status_code=400, detail="Maximum number of rented books reached")

    try:
        books_response = httpx.get(
            f"{LIBRARY_SERVICE_URL}/api/v1/libraries/{body.libraryUid}/books",
            params={
                "page": 1,
                "size": 100,
                "showAll": False,
            },
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Library Service is unavailable")
    
    if books_response.status_code != 200:
        raise HTTPException(status_code=books_response.status_code, detail="Unable to get library books")

    books = books_response.json()
    book = next(
        (book for book in books["items"]
        if book["bookUid"] == str(body.bookUid)),
        None
    )

    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")
    try:
        take_response = httpx.post(
            f"{LIBRARY_SERVICE_URL}/api/v1/libraries/"
            f"{body.libraryUid}/books/{body.bookUid}/take",
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Library Service is unavailable")

    if take_response.status_code != 200:
        raise HTTPException(status_code=take_response.status_code, detail="Unable to take book")

    try:
        reservation_response = httpx.post(
            f"{RESERVATION_SERVICE_URL}/api/v1/reservations",
            headers=headers,
            json=body.model_dump(mode="json"),
            timeout=5.0,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Reservation Service is unavailable")

    if reservation_response.status_code != 200:
        raise HTTPException(status_code=reservation_response.status_code, detail=reservation_response.text)

    reservation_data = reservation_response.json()
    library = get_library_info(str(reservation_data.get("libraryUid") or body.libraryUid))
    book = {
            "bookUid": book["bookUid"],
            "name": book["name"],
            "author": book["author"],
            "genre": book["genre"],
        }

    return JSONResponse(content={
        "reservationUid": str(reservation_data.get("reservationUid")),
        "status": reservation_data.get("status"),
        "startDate": to_date(reservation_data.get("startDate")).isoformat(),
        "tillDate": to_date(reservation_data.get("tillDate")).isoformat(),
        "book": book,
        "library": {
            "libraryUid": library["libraryUid"],
            "name": library["name"],
            "address": library["address"],
            "city": library["city"],
        },
        "rating": {"stars": stars},
    }, status_code=200)

@app.post("/api/v1/reservations/{reservation_uid}/return")
def return_reservation(reservation_uid: UUID, body: ReturnRequest, x_user_name: str = Header(..., alias="X-User-Name")):
    headers = {"X-User-Name": x_user_name}

    reservation_response = send_request(
        "GET",
        f"{RESERVATION_SERVICE_URL}/api/v1/reservations/{reservation_uid}",
        headers=headers,
        timeout=5.0,
    )

    if reservation_response is None:
        raise HTTPException(status_code=503, detail="Reservation Service is unavailable")

    if reservation_response.status_code != 200:
        raise HTTPException(
            status_code=reservation_response.status_code,
            detail=reservation_response.text,
        )

    reservation = reservation_response.json()

    if reservation["status"] != "RENTED":
        raise HTTPException(status_code=400, detail="Reservation is not active")

    book_uid = reservation["bookUid"]
    library_uid = reservation["libraryUid"]

    books_response = send_request(
        "GET",
        f"{LIBRARY_SERVICE_URL}/api/v1/libraries/{library_uid}/books",
        params={"page": 1, "size": 100, "showAll": True},
        timeout=5.0,
    )

    if books_response is None:
        raise HTTPException(status_code=503, detail="Library Service is unavailable")

    if books_response.status_code != 200:
        raise HTTPException(
            status_code=books_response.status_code,
            detail="Unable to get library books",
        )

    book = next(
        (
            item
            for item in books_response.json()["items"]
            if item["bookUid"] == str(book_uid)
        ),
        None,
    )

    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    is_late = to_date(body.date) > to_date(reservation["tillDate"])
    condition_changed = body.condition != book["condition"]

    delta = -10 if is_late or condition_changed else 1

    status_response = send_request(
        "POST",
        f"{RESERVATION_SERVICE_URL}/api/v1/reservations/"
        f"{reservation_uid}/return",
        headers=headers,
        json=body.model_dump(mode="json"),
        timeout=5.0,
    )

    if status_response is None:
        raise HTTPException(status_code=503, detail="Reservation Service is unavailable")

    if status_response.status_code not in (200, 204):
        raise HTTPException(
            status_code=status_response.status_code,
            detail=status_response.text,
        )

    library_url = (
        f"{LIBRARY_SERVICE_URL}/api/v1/libraries/"
        f"{library_uid}/books/{book_uid}/return"
    )

    library_response = retry_request(
        "POST",
        library_url,
        timeout=10,
    )

    if library_response is None or library_response.status_code not in (200, 204):
        enqueue({
            "type": "request",
            "username": x_user_name,
            "method": "POST",
            "url": library_url,
        })

    if not retry_rating_update(x_user_name, delta, timeout=10):
        enqueue({
            "type": "rating",
            "username": x_user_name,
            "delta": delta,
        })

    return Response(status_code=204)

# ---------------- RATING SERVICE ----------------

@app.get("/api/v1/rating")
def get_rating(x_user_name: str = Header(..., alias="X-User-Name"),):
    process_pending_for_user(x_user_name)
    return proxy_request(
        "GET",
        f"{RATING_SERVICE_URL}/api/v1/rating",
        headers={"X-User-Name": x_user_name},
        error_message="Bonus Service unavailable",
    )