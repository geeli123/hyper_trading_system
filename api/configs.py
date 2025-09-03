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
    # return full config object by filtering from all
    configs = ConfigManager.get_all_configs()
    for c in configs:
        if c["key"] == key:
            return c
    raise HTTPException(status_code=404, detail="Config not found")


@router.post("/", response_model=ConfigOut)
def upsert_config(payload: ConfigIn):
    ok = ConfigManager.set_config(
        key=payload.key,
        value=payload.value,
        description=payload.description or "",
        config_type=payload.config_type or "string",
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to upsert config")
    # return updated object
    return get_config(payload.key)


@router.delete("/{key}")
def delete_config(key: str):
    ok = ConfigManager.delete_config(key)
    if not ok:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"deleted": 1}


