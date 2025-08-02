from __future__ import annotations

"""Data access layer using SQLModel for persistence."""

from datetime import datetime, timedelta
from typing import List, Dict, Optional

from sqlmodel import SQLModel, Field, create_engine, Session, select
import os
from hashlib import sha256

from solbot.schema import PositionState, SCHEMA_HASH


class DBOrder(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    token: str
    quantity: float
    side: str
    price: float
    ts: datetime = Field(default_factory=datetime.utcnow)


class DBPosition(SQLModel, table=True):
    token: str = Field(primary_key=True)
    data: bytes


class DBAsset(SQLModel, table=True):
    symbol: str = Field(primary_key=True)
    mint: Optional[str] = None
    decimals: Optional[int] = None
    chain_id: Optional[int] = None


class DBPrice(SQLModel, table=True):
    token: str = Field(primary_key=True)
    price: float
    ts: datetime
    expiry: datetime


class DBMeta(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class DAL:
    """Handle SQLite persistence."""

    def __init__(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False}
        )
        SQLModel.metadata.create_all(self.engine)
        with Session(self.engine) as session:
            existing = session.get(DBMeta, "schema_hash")
            if existing and existing.value != SCHEMA_HASH:
                raise RuntimeError("schema hash mismatch")
            if not existing:
                session.add(DBMeta(key="schema_hash", value=SCHEMA_HASH))
            session.commit()

    def get_meta(self, key: str) -> Optional[str]:
        with Session(self.engine) as session:
            row = session.get(DBMeta, key)
            return row.value if row else None

    def set_meta(self, key: str, value: str) -> None:
        with Session(self.engine) as session:
            session.merge(DBMeta(key=key, value=value))
            session.commit()

    def add_order(self, order: DBOrder) -> DBOrder:
        with Session(self.engine) as session:
            session.add(order)
            session.commit()
            session.refresh(order)
        return order

    def list_orders(self) -> List[DBOrder]:
        with Session(self.engine) as session:
            return session.exec(select(DBOrder).order_by(DBOrder.id)).all()

    def upsert_position(self, pos: Optional[PositionState]) -> None:
        if not pos:
            return
        with Session(self.engine) as session:
            session.merge(DBPosition(token=pos.token, data=pos.SerializeToString()))
            session.commit()

    def remove_position(self, token: str) -> None:
        with Session(self.engine) as session:
            pos = session.get(DBPosition, token)
            if pos:
                session.delete(pos)
                session.commit()

    def load_positions(self) -> Dict[str, PositionState]:
        with Session(self.engine) as session:
            positions = session.exec(select(DBPosition)).all()
            out: Dict[str, PositionState] = {}
            for p in positions:
                state = PositionState()
                state.ParseFromString(p.data)
                out[p.token] = state
            return out

    def save_assets(self, assets: List[dict]) -> None:
        with Session(self.engine) as session:
            from sqlalchemy import delete

            session.exec(delete(DBAsset))
            for a in assets:
                session.add(
                    DBAsset(
                        symbol=a.get("symbol"),
                        mint=a.get("address"),
                        decimals=a.get("decimals"),
                        chain_id=a.get("chainId"),
                    )
                )
            session.commit()

    def list_assets(self) -> List[dict]:
        with Session(self.engine) as session:
            return [a.dict() for a in session.exec(select(DBAsset)).all()]

    def cache_price(self, token: str, price: float, ttl: int = 30) -> None:
        exp = datetime.utcnow() + timedelta(seconds=ttl)
        with Session(self.engine) as session:
            session.merge(
                DBPrice(token=token, price=price, ts=datetime.utcnow(), expiry=exp)
            )
            session.commit()

    def last_price(self, token: str) -> Optional[float]:
        with Session(self.engine) as session:
            p = session.get(DBPrice, token)
            if not p:
                return None
            if p.expiry < datetime.utcnow():
                session.delete(p)
                session.commit()
                return None
            return p.price
