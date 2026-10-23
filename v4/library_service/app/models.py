from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from .db import Base


class Library(Base):
    __tablename__ = "library"

    id = Column(Integer, primary_key=True)
    library_uid = Column(UUID(as_uuid=True), unique=True, nullable=False)
    name = Column(String(80), nullable=False)
    city = Column(String(255), nullable=False)
    address = Column(String(255), nullable=False)


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True)
    book_uid = Column(UUID(as_uuid=True), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    author = Column(String(255))
    genre = Column(String(255))
    condition = Column(String(20), default="EXCELLENT")


class LibraryBook(Base):
    __tablename__ = "library_books"

    book_id = Column(Integer, ForeignKey("books.id"), primary_key=True)
    library_id = Column(Integer, ForeignKey("library.id"), primary_key=True)
    available_count = Column(Integer, nullable=False)