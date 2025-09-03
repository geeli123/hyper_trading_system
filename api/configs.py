from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from config.config_manager import ConfigManager

router = APIRouter(prefix="/configs", tags=["configs"])


class ConfigIn(BaseModel):
    key: str
    value: str
    description: Optional[str] = None
    config_type: Optional[str] = "string"


class ConfigOut(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str]
    config_type: str
    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=List[ConfigOut])
def list_configs():
    return ConfigManager.get_all_configs()


@router.get("/{key}", response_model=ConfigOut)
def get_config(key: str):
    obj = ConfigManager.get_config(key)
    if not obj:
        raise HTTPException(status_code=404, detail="Config not found")
    return obj


@router.post("/", response_model=ConfigOut)
def upsert_config(payload: ConfigIn):
    return ConfigManager.set_config(
        key=payload.key,
        value=payload.value,
        description=payload.description,
        config_type=payload.config_type,
    )


@router.delete("/{key}")
def delete_config(key: str):
    n = ConfigManager.delete_config(key)
    if n == 0:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"deleted": n}


