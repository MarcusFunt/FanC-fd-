from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.models.api_types import JobCreateRequest, JobLogResponse, JobResponse
from api.services.job_manager import job_manager

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("/", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_job(request: JobCreateRequest) -> dict:
    try:
        record = await job_manager.launch_job(
            job_type=request.type,
            config_id=request.config_id,
            options=request.options,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return record.to_dict()


@router.get("/", response_model=list[JobResponse])
def list_jobs() -> list[dict]:
    return [job.to_dict() for job in job_manager.list_jobs()]


@router.get("/{job_id}/logs", response_model=JobLogResponse)
def get_job_logs(job_id: str) -> dict:
    record = job_manager.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"job_id": job_id, "lines": job_manager.get_logs(record)}


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> dict:
    record = job_manager.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return record.to_dict()


@router.delete("/{job_id}", response_model=JobResponse)
async def cancel_job(job_id: str) -> dict:
    record = job_manager.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    await job_manager.cancel_job(job_id)
    return record.to_dict()

