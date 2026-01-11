from __future__ import annotations

import os
import uuid
from datetime import datetime

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .db import Base, engine, get_session
from .models import Artifact, JobRun
from .schemas import ArtifactListOut, ArtifactOut, JobRunCreate, JobRunOut
from .storage import Storage

app = FastAPI(title="HWCI API", version="0.1.0")
storage = Storage()


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    storage.ensure_bucket()


@app.post("/runs", response_model=JobRunOut)
def create_run(payload: JobRunCreate, session: Session = Depends(get_session)) -> JobRun:
    run = JobRun(status=payload.status, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


@app.get("/runs/{run_id}", response_model=JobRunOut)
def get_run(run_id: uuid.UUID, session: Session = Depends(get_session)) -> JobRun:
    run = session.get(JobRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.post("/runs/{run_id}/artifacts", response_model=ArtifactOut)
def upload_artifact(
    run_id: uuid.UUID,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> Artifact:
    run = session.get(JobRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)

    filename = file.filename or "artifact"
    s3_key = f"runs/{run_id}/{uuid.uuid4()}-{filename}"
    storage.put_object(s3_key, file.file, file.content_type)

    artifact = Artifact(
        run_id=run_id,
        name=filename,
        s3_key=s3_key,
        content_type=file.content_type,
        size=size,
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


@app.get("/runs/{run_id}/artifacts", response_model=ArtifactListOut)
def list_artifacts(run_id: uuid.UUID, session: Session = Depends(get_session)) -> ArtifactListOut:
    run = session.get(JobRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    items = session.query(Artifact).filter(Artifact.run_id == run_id).order_by(Artifact.created_at.asc()).all()
    return ArtifactListOut(items=items)


@app.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: uuid.UUID, session: Session = Depends(get_session)) -> dict:
    artifact = session.get(Artifact, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="artifact not found")
    url = storage.presign_get(artifact.s3_key)
    return {"url": url, "expires_in": 3600}
