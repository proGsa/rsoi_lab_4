from fastapi import Depends, FastAPI, Header, HTTPException, Response
from sqlalchemy.orm import Session

from .db import get_db
from . import models, schemas
from uuid import uuid4
from datetime import date, datetime
from uuid import UUID


app = FastAPI(title="Reservation Service")


def to_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value

@app.get("/manage/health")
def health():
    return {"status": "ok"}

@app.get("/api/v1/reservations", response_model=list[schemas.ReservationResponse])
def get_reservations(x_user_name: str = Header(...), db: Session = Depends(get_db)):
    reservations = db.query(models.Reservation).filter(models.Reservation.username == x_user_name, models.Reservation.status == "RENTED").all()

    return [
        {
            "reservationUid": reservation.reservation_uid,
            "startDate": reservation.start_date,
            "tillDate": reservation.till_date,
            "bookUid": reservation.book_uid,
            "libraryUid": reservation.library_uid, 
            "status": reservation.status,
        }
        for reservation in reservations
    ]

@app.post("/api/v1/reservations", response_model=schemas.ReservationResponse)
def create_reservation(request: schemas.ReservationRequest, x_user_name: str = Header(...), db: Session = Depends(get_db)):
    reservation = models.Reservation(
        reservation_uid=uuid4(),
        username=x_user_name,
        book_uid=request.book_uid,
        library_uid=request.library_uid,
        status="RENTED",
        start_date=date.today(),
        till_date=request.till_date,
    )

    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return {
        "reservationUid": reservation.reservation_uid,
        "startDate": reservation.start_date,
        "tillDate": reservation.till_date,
        "bookUid": reservation.book_uid,
        "libraryUid": reservation.library_uid,
        "status": reservation.status,
    }

@app.post("/api/v1/reservations/{reservation_uid}/return")
def return_reservation(reservation_uid: str, request: schemas.ReturnRequest, x_user_name: str = Header(...), db: Session = Depends(get_db)):
    reservation = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.reservation_uid == reservation_uid,
            models.Reservation.username == x_user_name,
        )
        .first()
    )

    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if reservation.status != "RENTED":
        raise HTTPException(status_code=400, detail="Reservation is not active")

    return_date = to_date(request.date)
    till_date = to_date(reservation.till_date)

    if return_date > till_date:
        reservation.status = "EXPIRED"
    else:
        reservation.status = "RETURNED"

    db.commit()

    return Response(status_code=204)

@app.get("/api/v1/reservations/{reservation_uid}", response_model=schemas.ReservationResponse)
def get_reservation(reservation_uid: UUID, x_user_name: str = Header(...), db: Session = Depends(get_db)):
    reservation = (
        db.query(models.Reservation)
        .filter(
            models.Reservation.reservation_uid == reservation_uid,
            models.Reservation.username == x_user_name,
        )
        .first()
    )

    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    

    return {
        "reservationUid": reservation.reservation_uid,
        "startDate": reservation.start_date,
        "tillDate": reservation.till_date,
        "bookUid": reservation.book_uid,
        "libraryUid": reservation.library_uid,
        "status": reservation.status,
    }
