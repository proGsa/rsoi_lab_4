from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookInfo(BaseModel):
    book_uid: UUID = Field(alias="bookUid")
    name: str
    author: str | None
    genre: str | None

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class LibraryInfo(BaseModel):
    library_uid: UUID = Field(alias="libraryUid")
    name: str
    address: str
    city: str

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class BookReservationResponse(BaseModel):
    reservation_uid: UUID = Field(alias="reservationUid")
    status: str
    start_date: date = Field(alias="startDate")
    till_date: date = Field(alias="tillDate")
    book: BookInfo
    library: LibraryInfo

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ReservationRequest(BaseModel):
    book_uid: UUID = Field(alias="bookUid")
    library_uid: UUID = Field(alias="libraryUid")
    till_date: date = Field(alias="tillDate")

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class ReservationResponse(BaseModel):
    reservationUid: UUID
    status: str
    startDate: date
    tillDate: date
    bookUid: UUID
    libraryUid: UUID

class ReturnRequest(BaseModel):
    condition: str
    date: date

class UserRatingResponse(BaseModel):
    stars: int

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

class TakeBookResponse(BaseModel):
    reservation_uid: UUID = Field(alias="reservationUid")
    status: str
    start_date: date = Field(alias="startDate")
    till_date: date = Field(alias="tillDate")
    book: BookInfo
    library: LibraryInfo
    rating: UserRatingResponse

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)