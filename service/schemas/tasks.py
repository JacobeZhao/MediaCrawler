from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..providers.justoneapi.options import (
    NoteType,
    PAGE_LIMIT_MAX,
    PAGE_LIMIT_MIN,
    REQUEST_BUDGET_MAX,
    REQUEST_BUDGET_MIN,
    TASK_OPTION_DEFAULTS,
    TRANSPORT_SORT_TYPE_DEFAULT,
    TimeFilter,
)


TaskProviderName = Literal["local", "justoneapi"]


class JustOneApiOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_details: bool = TASK_OPTION_DEFAULTS.include_details
    include_comments: bool = TASK_OPTION_DEFAULTS.include_comments
    include_replies: bool = TASK_OPTION_DEFAULTS.include_replies
    max_pages: int = Field(
        default=TASK_OPTION_DEFAULTS.max_pages,
        ge=PAGE_LIMIT_MIN,
        le=PAGE_LIMIT_MAX,
    )
    max_requests: int = Field(
        default=TASK_OPTION_DEFAULTS.max_requests,
        ge=REQUEST_BUDGET_MIN,
        le=REQUEST_BUDGET_MAX,
    )
    note_type: NoteType = TASK_OPTION_DEFAULTS.note_type
    time_filter: TimeFilter = TASK_OPTION_DEFAULTS.time_filter

    @model_validator(mode="after")
    def validate_reply_options(self):
        if self.include_replies and not self.include_comments:
            raise ValueError("include_replies requires include_comments")
        return self


class ProviderTaskRequest(BaseModel):
    provider: TaskProviderName = "local"
    provider_options: Optional[JustOneApiOptions] = None


class SearchTaskRequest(ProviderTaskRequest):
    keyword: str = Field(min_length=1, max_length=200)
    max_notes: int = Field(default=20, ge=1, le=500)
    max_comments: int = Field(default=20, ge=0, le=10000)
    force: bool = False
    sort_type: str = Field(default="popularity_descending", pattern="^(popularity_descending|time_descending|general)$")
    days_limit: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_provider_search_options(self):
        if self.provider == "justoneapi":
            if self.days_limit:
                raise ValueError(
                    "days_limit is only supported by local; use provider_options.time_filter"
                )
            if "sort_type" not in self.model_fields_set:
                self.sort_type = TRANSPORT_SORT_TYPE_DEFAULT
        return self


class CreatorTaskRequest(ProviderTaskRequest):
    creator_input: str = Field(min_length=1, max_length=500)
    max_notes: int = Field(default=20, ge=1, le=500)
    force: bool = False


class BatchSearchTaskRequest(ProviderTaskRequest):
    keywords: List[str] = Field(min_length=1, max_length=200)
    max_notes: int = Field(default=20, ge=1, le=500)
    max_comments: int = Field(default=20, ge=0, le=10000)
    sort_type: str = Field(default="popularity_descending", pattern="^(popularity_descending|time_descending|general)$")
    days_limit: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_provider_search_options(self):
        if self.provider == "justoneapi":
            if self.days_limit:
                raise ValueError(
                    "days_limit is only supported by local; use provider_options.time_filter"
                )
            if "sort_type" not in self.model_fields_set:
                self.sort_type = TRANSPORT_SORT_TYPE_DEFAULT
        return self


class BatchCreatorTaskRequest(ProviderTaskRequest):
    creator_urls: List[str] = Field(min_length=1, max_length=200)
    max_notes: int = Field(default=20, ge=1, le=500)


class NoteItem(BaseModel):
    note_input: str = Field(min_length=1, max_length=500)
    d_level: str = Field(min_length=1, max_length=20)
    quality: str = Field(min_length=1, max_length=50)


class NoteTaskRequest(ProviderTaskRequest):
    notes: List[NoteItem] = Field(min_length=1, max_length=200)
    max_comments: int = Field(default=0, ge=0, le=10000)
    include_replies: bool = False

    @model_validator(mode="after")
    def validate_comment_scope(self):
        if self.include_replies and self.max_comments == 0:
            raise ValueError("include_replies requires max_comments greater than zero")
        if (
            self.provider == "justoneapi"
            and self.provider_options
            and self.provider_options.include_comments
            and "max_comments" in self.model_fields_set
            and self.max_comments == 0
        ):
            raise ValueError(
                "max_comments must be greater than zero when include_comments is enabled"
            )
        return self
