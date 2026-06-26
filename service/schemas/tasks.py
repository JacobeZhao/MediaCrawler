from typing import List

from pydantic import BaseModel, Field


class SearchTaskRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    max_notes: int = Field(default=20, ge=1, le=500)
    max_comments: int = Field(default=20, ge=0, le=10000)
    force: bool = False
    sort_type: str = Field(default="popularity_descending", pattern="^(popularity_descending|time_descending|general)$")
    days_limit: int = Field(default=0, ge=0)


class CreatorTaskRequest(BaseModel):
    creator_input: str = Field(min_length=1, max_length=500)
    max_notes: int = Field(default=20, ge=1, le=500)
    force: bool = False


class BatchSearchTaskRequest(BaseModel):
    keywords: List[str] = Field(min_length=1, max_length=200)
    max_notes: int = Field(default=20, ge=1, le=500)
    max_comments: int = Field(default=20, ge=0, le=10000)
    sort_type: str = Field(default="popularity_descending", pattern="^(popularity_descending|time_descending|general)$")
    days_limit: int = Field(default=0, ge=0)


class BatchCreatorTaskRequest(BaseModel):
    creator_urls: List[str] = Field(min_length=1, max_length=200)
    max_notes: int = Field(default=20, ge=1, le=500)


class NoteItem(BaseModel):
    note_input: str = Field(min_length=1, max_length=500)
    d_level: str = Field(min_length=1, max_length=20)
    quality: str = Field(min_length=1, max_length=50)


class NoteTaskRequest(BaseModel):
    notes: List[NoteItem] = Field(min_length=1, max_length=200)
