from sqlalchemy import Column, Integer, String

from .db import Base


class Rating(Base):
    __tablename__ = "rating"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), nullable=False)
    stars = Column(Integer, nullable=False)