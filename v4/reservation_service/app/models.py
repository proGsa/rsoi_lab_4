from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from .db import Base


class Reservation(Base):
    __tablename__ = "reservation"

    id = Column(Integer, primary_key=True)

    reservation_uid = Column(UUID(as_uuid=True), unique=True, nullable=False)
    username = Column(String(80), nullable=False)
    book_uid = Column(UUID(as_uuid=True), nullable=False)
    library_uid = Column(UUID(as_uuid=True), nullable=False,)
    status = Column(String(20), nullable=False)
    start_date = Column(DateTime, nullable=False)
    till_date = Column(DateTime, nullable=False)