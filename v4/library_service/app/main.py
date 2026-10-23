from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Header
from sqlalchemy.orm import Session

from . import models, schemas
from .schemas import BooksResponse
from .db import get_db

app = FastAPI(title="Library Service")

@app.get("/manage/health")
def health():
    return {"status": "ok"}

@app.get("/api/v1/libraries", response_model=schemas.LibrariesResponse)
def get_libraries(city: str, page: int = Query(1, ge=1), size: int = Query(10, ge=1), db: Session = Depends(get_db)):
    query = (db.query(models.Library).filter(models.Library.city == city))

    total_elements = query.count()

    libraries = (query.offset((page-1) * size).limit(size).all())

    return {
        "page": page,
        "pageSize": size,
        "totalElements": total_elements,
        "items": libraries,
    }

@app.get("/api/v1/libraries/{library_uid}/books", response_model=BooksResponse)
def get_books(library_uid: UUID, page: int = Query(1, ge=1), size: int = Query(10, ge=1), showAll: bool = False, db: Session = Depends(get_db)):
    library = (db.query(models.Library).filter(models.Library.library_uid == library_uid).first())

    if library is None:
        raise HTTPException(status_code=404, detail="Library not found")

    query = (
        db.query(models.Book, models.LibraryBook.available_count)
        .join(models.LibraryBook, models.Book.id == models.LibraryBook.book_id)
        .filter(models.LibraryBook.library_id == library.id)
    )

    if not showAll:
        query = query.filter(models.LibraryBook.available_count > 0)

    total_elements = query.count()
    
    results = (query.offset((page-1) * size).limit(size).all())


    return {
        "page": page,
        "pageSize": size,
        "totalElements": total_elements,
        "items": [
            schemas.BookResponse(
                book_uid=book.book_uid,
                name=book.name,
                author=book.author,
                genre=book.genre,
                condition=book.condition,
                availableCount=available_count,
            )
            for book, available_count in results
        ],
    }

@app.get("/api/v1/libraries/{library_uid}", response_model=schemas.LibraryResponse)
def get_library(library_uid: UUID, db: Session = Depends(get_db)):
    library = db.query(models.Library).filter(models.Library.library_uid == library_uid).first()

    if library is None:
        raise HTTPException(status_code=404, detail="Library not found")

    return library

@app.post("/api/v1/libraries/{library_uid}/books/{book_uid}/take")
def take_book(library_uid: UUID, book_uid: UUID, db: Session = Depends(get_db)):
    library_book = (
        db.query(models.LibraryBook)
        .join(models.Library)
        .join(models.Book)
        .filter(
            models.Library.library_uid == library_uid,
            models.Book.book_uid == book_uid,
        )
        .first()
    )

    if library_book is None:
        raise HTTPException(
            status_code=404,
            detail="Book not found in this library",
        )

    if library_book.available_count <= 0:
        raise HTTPException(
            status_code=400,
            detail="Book is not available",
        )

    library_book.available_count -= 1

    db.commit()
    db.refresh(library_book)

    return {
        "book_uid": str(book_uid),
        "library_uid": str(library_uid),
        "availableCount": library_book.available_count,
    }

@app.post("/api/v1/libraries/{library_uid}/books/{book_uid}/return")
def return_book(library_uid: UUID, book_uid: UUID, db: Session = Depends(get_db)):
    library_book = (
        db.query(models.LibraryBook)
        .join(models.Library)
        .join(models.Book)
        .filter(
            models.Library.library_uid == library_uid,
            models.Book.book_uid == book_uid,
        ).first()
    )

    if library_book is None:
        raise HTTPException(status_code=404, detail="Book not found in this library")

    library_book.available_count += 1

    db.commit()
    db.refresh(library_book)

    return {
        "bookUid": str(book_uid),
        "libraryUid": str(library_uid),
        "availableCount": library_book.available_count,
    }