from pydantic import BaseModel, Field


class UserRatingResponse(BaseModel):
    stars: int = Field(ge=1, le=100)