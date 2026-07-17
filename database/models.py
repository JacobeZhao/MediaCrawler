from sqlalchemy import BigInteger, Column, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class XhsCreator(Base):
    __tablename__ = "xhs_creator"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), index=True, unique=True)
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    desc = Column(Text)
    gender = Column(Text)
    follows = Column(Text)
    fans = Column(Text)
    interaction = Column(Text)
    tag_list = Column(Text)


class XhsNote(Base):
    __tablename__ = "xhs_note"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    note_id = Column(String(255), index=True, unique=True)
    type = Column(Text)
    title = Column(Text)
    desc = Column(Text)
    video_url = Column(Text)
    time = Column(BigInteger, index=True)
    last_update_time = Column(BigInteger)
    liked_count = Column(Text)
    collected_count = Column(Text)
    comment_count = Column(Text)
    share_count = Column(Text)
    image_list = Column(Text)
    tag_list = Column(Text)
    note_url = Column(Text)
    source_keyword = Column(Text, default="")
    xsec_token = Column(Text)


class XhsNoteComment(Base):
    __tablename__ = "xhs_note_comment"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(255))
    nickname = Column(Text)
    avatar = Column(Text)
    ip_location = Column(Text)
    add_ts = Column(BigInteger)
    last_modify_ts = Column(BigInteger)
    comment_id = Column(String(255), index=True, unique=True)
    create_time = Column(BigInteger, index=True)
    note_id = Column(String(255), index=True)
    content = Column(Text)
    sub_comment_count = Column(Integer)
    pictures = Column(Text)
    parent_comment_id = Column(String(255))
    like_count = Column(Text)


class XhsContentSource(Base):
    __tablename__ = "xhs_content_source"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "entity_id",
            "provider",
            "task_id",
            "source_keyword",
            name="uq_xhs_content_source_attribution",
        ),
    )

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(32), nullable=False, index=True)
    entity_id = Column(String(255), nullable=False, index=True)
    provider = Column(String(32), nullable=False)
    task_id = Column(Integer, nullable=False, default=0, index=True)
    source_keyword = Column(Text, nullable=False, default="")
    first_seen_ts = Column(BigInteger, nullable=False)
    last_seen_ts = Column(BigInteger, nullable=False)
