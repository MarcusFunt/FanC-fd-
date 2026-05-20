from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status

from api.models.api_types import (
    ConfigDetail,
    ConfigListItem,
    ConfigSaveRequest,
    ValidationRequest,
    ValidationResponse,
)
from api.services.config_validator import (
    create_config,
    delete_config,
    get_config,
    list_configs,
    update_config,
    validate_config_payload,
)
from api.services.schema_exporter import get_config_schema

router = APIRouter(prefix="/api/v1/configs", tags=["configs"])


@router.get("/", response_model=list[ConfigListItem])
def list_saved_configs() -> list[dict]:
    return list_configs()


@router.get("/schema")
def schema() -> dict:
    return get_config_schema()


@router.post("/validate", response_model=ValidationResponse)
def validate_config(request: ValidationRequest) -> dict:
    return validate_config_payload(request.yaml_text, request.data)


@router.post("/", response_model=ConfigDetail, status_code=status.HTTP_201_CREATED)
def save_config(request: ConfigSaveRequest) -> dict:
    try:
        result = create_config(request.id, request.yaml_text, request.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=400, detail="Config payload is required.")
    return result


@router.get("/{config_id}", response_model=ConfigDetail)
def load_config(config_id: str) -> dict:
    result = get_config(config_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Config not found.")
    return result


@router.put("/{config_id}", response_model=ConfigDetail)
def replace_config(config_id: str, request: ConfigSaveRequest) -> dict:
    try:
        result = update_config(config_id, request.yaml_text, request.data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Config not found.")
    return result


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def remove_config(config_id: str) -> Response:
    deleted = delete_config(config_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
