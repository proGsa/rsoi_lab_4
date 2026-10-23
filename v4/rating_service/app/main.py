from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from .db import get_db
from pydantic import BaseModel

class RatingUpdate(BaseModel):
    stars: int

app = FastAPI(title="Rating Service")

@app.get("/manage/health")
def health():
    return {"status": "ok"}

@app.get("/api/v1/rating", response_model=schemas.UserRatingResponse)
def get_rating(x_user_name: str = Header(...), db: Session = Depends(get_db)):
    rating = (
        db.query(models.Rating)
        .filter(models.Rating.username == x_user_name)
        .first()
    )

    if rating is None:
        raise HTTPException(
            status_code=404,
            detail="Rating not found",
        )

    return rating

@app.patch("/api/v1/rating")
def update_rating(body: RatingUpdate, x_user_name: str = Header(..., alias="X-User-Name"), db: Session = Depends(get_db)):
    rating = (
        db.query(models.Rating)
        .filter(models.Rating.username == x_user_name)
        .first()
    )

    if rating is None:
        raise HTTPException(status_code=404, detail="Rating not found")

    rating.stars = max(1, min(100, body.stars))

    db.commit()
    db.refresh(rating)

    return {
        "stars": rating.stars
    }