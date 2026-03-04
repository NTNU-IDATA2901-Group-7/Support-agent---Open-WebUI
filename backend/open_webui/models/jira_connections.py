import time
import logging
from typing import Optional

from sqlalchemy.orm import Session
from open_webui.internal.db import Base

from pydantic import BaseModel
from sqlalchemy import Column, String, Text, BigInteger, Index

log = logging.getLogger(__name__)

####################
# DB MODEL
####################


class JiraConnection(Base):
    __tablename__ = "jira_connection"

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(String, nullable=False, unique=True)
    atlassian_account_id = Column(String, nullable=False)
    cloud_id = Column(String, nullable=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    expires_at = Column(BigInteger, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)

    __table_args__ = (
        Index("idx_jira_connection_user_id", "user_id"),
        Index("idx_jira_connection_atlassian_account_id", "atlassian_account_id"),
    )


####################
# PYDANTIC MODELS
####################


class JiraConnectionModel(BaseModel):
    id: str
    user_id: str
    atlassian_account_id: str
    cloud_id: Optional[str] = None
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: int
    created_at: int
    updated_at: int

    class Config:
        from_attributes = True


class JiraConnectionForm(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: int
    atlassian_account_id: str


####################
# FUNCTIONS
####################


class JiraConnections:
    @staticmethod
    def insert_new_connection(
        user_id: str,
        atlassian_account_id: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_at: int,
        cloud_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> JiraConnectionModel:
        from open_webui.internal.db import get_session

        if db is None:
            db = next(get_session())

        result = db.query(JiraConnection).filter_by(user_id=user_id).first()

        if result:
            result.atlassian_account_id = atlassian_account_id
            result.cloud_id = cloud_id
            result.access_token = access_token
            result.refresh_token = refresh_token
            result.expires_at = expires_at
            result.updated_at = int(time.time())
        else:
            result = JiraConnection(
                id=f"{user_id}_{atlassian_account_id}",
                user_id=user_id,
                atlassian_account_id=atlassian_account_id,
                cloud_id=cloud_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                created_at=int(time.time()),
                updated_at=int(time.time()),
            )
            db.add(result)

        db.commit()
        return JiraConnectionModel.model_validate(result)

    @staticmethod
    def get_connection_by_user_id(
        user_id: str, db: Optional[Session] = None
    ) -> Optional[JiraConnectionModel]:
        from open_webui.internal.db import get_session

        if db is None:
            db = next(get_session())

        result = db.query(JiraConnection).filter_by(user_id=user_id).first()
        return JiraConnectionModel.model_validate(result) if result else None

    @staticmethod
    def delete_connection_by_user_id(
        user_id: str, db: Optional[Session] = None
    ) -> bool:
        from open_webui.internal.db import get_session

        if db is None:
            db = next(get_session())

        result = db.query(JiraConnection).filter_by(user_id=user_id).first()

        if result:
            db.delete(result)
            db.commit()
            return True
        return False
