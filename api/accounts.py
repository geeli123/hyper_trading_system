from typing import Optional

from eth_account import Account as EthAccount
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from database.models import Account
from database.session import SessionLocal
from utils.response import ApiResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountIn(BaseModel):
    alias: str
    account_address: str
    secret_key: str
    is_active: Optional[bool] = True


class AccountOut(BaseModel):
    id: int
    alias: str
    account_address: str
    api_wallet_address: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


@router.get("/")
def list_accounts():
    db = SessionLocal()
    try:
        items = db.query(Account).all()
        return ApiResponse.success([AccountOut.model_validate(i).model_dump() for i in items])
    finally:
        db.close()


@router.post("/")
def upsert_account(payload: AccountIn):
    db = SessionLocal()
    try:
        obj = db.query(Account).filter_by(alias=payload.alias).first()
        # derive account address from secret key
        derived_address = EthAccount.from_key(payload.secret_key).address
        if obj:
            obj.account_address = payload.account_address
            obj.api_wallet_address = derived_address
            obj.secret_key = payload.secret_key
            obj.is_active = payload.is_active if payload.is_active is not None else obj.is_active
        else:
            obj = Account(
                alias=payload.alias,
                account_address=payload.account_address,
                api_wallet_address=derived_address,
                secret_key=payload.secret_key,
                is_active=payload.is_active if payload.is_active is not None else True,
            )
            db.add(obj)
        db.commit()
        db.refresh(obj)
        return ApiResponse.success(AccountOut.model_validate(obj).model_dump(), "saved")
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
        return ApiResponse.success({"deleted": n})
    finally:
        db.close()
