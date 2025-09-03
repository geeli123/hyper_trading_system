from typing import List, Optional

from eth_account import Account as EthAccount
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from database.models import Account
from database.session import SessionLocal

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountIn(BaseModel):
    alias: str
    api_wallet_address: str
    secret_key: str
    is_active: Optional[bool] = True


class AccountOut(BaseModel):
    id: int
    alias: str
    account_address: str
    api_wallet_address: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[AccountOut])
def list_accounts():
    db = SessionLocal()
    try:
        return db.query(Account).all()
    finally:
        db.close()


@router.post("/", response_model=AccountOut)
def upsert_account(payload: AccountIn):
    db = SessionLocal()
    try:
        obj = db.query(Account).filter_by(alias=payload.alias).first()
        # derive account address from secret key
        derived_address = EthAccount.from_key(payload.secret_key).address
        if obj:
            obj.account_address = derived_address
            obj.api_wallet_address = payload.api_wallet_address
            obj.secret_key = payload.secret_key
            obj.is_active = payload.is_active if payload.is_active is not None else obj.is_active
        else:
            obj = Account(
                alias=payload.alias,
                account_address=derived_address,
                api_wallet_address=payload.api_wallet_address,
                secret_key=payload.secret_key,
                is_active=payload.is_active if payload.is_active is not None else True,
            )
            db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    finally:
        db.close()


@router.delete("/{alias}")
def delete_account(alias: str):
    db = SessionLocal()
    try:
        n = db.query(Account).filter_by(alias=alias).delete()
        if n == 0:
            raise HTTPException(status_code=404, detail="Account not found")
        db.commit()
        return {"deleted": n}
    finally:
        db.close()


