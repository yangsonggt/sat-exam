"""Upload router: PDF upload, list, status, delete."""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
import os

from app.database import get_db
from app.dependencies import get_current_user, require_role
from app.models import User
from app.upload import service
from app.upload.schemas import UploadResponse, UploadListResponse, ParseStatusResponse

router = APIRouter(prefix="/api/v1/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Upload a PDF file for question extraction."""
    return await service.upload_file(db, file, user)


@router.get("", response_model=UploadListResponse)
async def list_uploads(
    offset: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """List all uploads (paginated)."""
    items, total = await service.list_uploads(db, offset, limit)
    return UploadListResponse(items=items, total=total, offset=offset, limit=limit)


# ── Parse job endpoints (must come before /{upload_id} wildcard) ──

_parse_jobs: dict[str, dict] = {}


@router.post("/parse", response_model=None)
async def upload_and_parse_pdf(
    file: UploadFile = File(...),
    answer_file: UploadFile | None = File(None),
    user: User = Depends(require_role("admin", "editor")),
):
    """Upload a question PDF + optional answer PDF, start background OCR parsing."""
    import tempfile
    import uuid
    import threading
    
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    job_id = uuid.uuid4().hex
    display_name = file.filename
    if answer_file and answer_file.filename:
        display_name += " + answers"

    _parse_jobs[job_id] = {"status": "saving", "filename": display_name, "result": None}

    # Save question PDF
    ext = file.filename.rsplit(".", 1)[-1]
    tmp_q = Path(tempfile.gettempdir()) / f"sat_q_{job_id}.{ext}"
    tmp_q.write_bytes(await file.read())

    # Save answer PDF if provided
    tmp_a = None
    if answer_file and answer_file.filename and answer_file.filename.lower().endswith(".pdf"):
        ext_a = answer_file.filename.rsplit(".", 1)[-1]
        tmp_a = Path(tempfile.gettempdir()) / f"sat_a_{job_id}.{ext_a}"
        tmp_a.write_bytes(await answer_file.read())

    # Also persist to DB
    import asyncio as _asyncio
    _asyncio.create_task(_save_activity(job_id, filename=display_name, status="saving"))

    threading.Thread(target=_run_parse_job_sync, args=(job_id, str(tmp_q), str(tmp_a) if tmp_a else None), daemon=True).start()
    return {"job_id": job_id, "filename": display_name, "status": "saving"}


@router.get("/parse")
async def list_parse_jobs():
    """List all parse jobs (from memory + DB history)."""
    jobs = [{"job_id": jid, **job} for jid, job in _parse_jobs.items()]
    
    # Also load from DB for jobs that survived restart
    try:
        from app.database import AsyncSessionLocal
        from app.models import ParseActivity
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(ParseActivity).order_by(ParseActivity.created_at.desc()))
            for row in r.scalars().all():
                # Don't duplicate in-memory jobs
                if any(j["job_id"] == row.job_id for j in jobs):
                    continue
                jobs.append({
                    "job_id": row.job_id,
                    "filename": row.filename,
                    "status": row.status,
                    "error": row.error,
                    "result": {
                        "questions_parsed": row.questions_parsed or 0,
                        "answers_matched": row.answers_matched or 0,
                        "questions_imported": row.questions_imported or 0,
                        "questions_skipped": row.questions_skipped or 0,
                    } if row.status in ("done", "error") else None,
                })
    except Exception:
        pass

    return {"jobs": jobs, "total": len(jobs)}


@router.get("/parse/{job_id}", response_model=None)
async def get_parse_status(job_id: str):
    """Poll parse job status. Returns result when complete."""
    job = _parse_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


# ── Upload detail routes ──


@router.get("/{upload_id}", response_model=UploadResponse)
async def get_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Get upload details."""
    return await service.get_upload(db, upload_id)


@router.get("/{upload_id}/status", response_model=ParseStatusResponse)
async def get_parse_status(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Get parsing status for an upload."""
    upload = await service.get_upload(db, upload_id)

    # Get latest parse job
    from sqlalchemy import select
    from app.models import ParseJob
    result = await db.execute(
        select(ParseJob)
        .where(ParseJob.upload_id == upload_id)
        .order_by(ParseJob.started_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()

    return ParseStatusResponse(
        upload_id=upload_id,
        status=upload.status,
        error=job.error if job else None,
    )


@router.delete("/{upload_id}")
async def delete_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("admin", "editor")),
):
    """Delete an upload. Published questions are preserved."""
    await service.delete_upload(db, upload_id)
    return {"ok": True}


@router.post("/images")
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(require_role("admin", "editor")),
):
    """Upload an image for use in question stems/options."""
    import uuid
    from pathlib import Path

    ext = file.filename.split(".")[-1].lower() if file.filename else "png"
    if ext not in ("png", "jpg", "jpeg", "gif", "svg", "webp"):
        raise HTTPException(400, "Invalid image format")

    name = f"{uuid.uuid4().hex}.{ext}"
    uploads_dir = Path("uploads/images")
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / name).write_bytes(await file.read())

    return {"url": f"/uploads/images/{name}"}


# ── Background parse helpers ──


async def _save_activity(job_id: str, **kwargs):
    """Persist job status to DB (non-blocking if DB is unavailable)."""
    try:
        from app.database import AsyncSessionLocal
        from app.models import ParseActivity
        from sqlalchemy import select, update
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(ParseActivity).where(ParseActivity.job_id == job_id))
            existing = r.scalar_one_or_none()
            if existing:
                for k, v in kwargs.items():
                    setattr(existing, k, v)
            else:
                db.add(ParseActivity(job_id=job_id, **kwargs))
            await db.commit()
    except Exception:
        pass


def _run_parse_job_sync(job_id: str, q_path: str, a_path: str | None = None):
    """Run the async parse job in a new event loop (thread-safe wrapper)."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_run_parse_job_async(job_id, q_path, a_path))


async def _run_parse_job_async(job_id: str, q_path: str, a_path: str | None = None):
    """Background task: OCR the PDF and import questions."""
    try:
        _parse_jobs[job_id]["status"] = "parsing"
        await _save_activity(job_id, status="parsing")
        
        parser = None
        try:
            from ocr_parser_v2 import HybridOCRParser
            parser = HybridOCRParser(dpi=200)
        except ImportError:
            from ocr_parser import OCRParser as OCP
            parser = OCP(dpi=200)

        result = parser.parse_full_document(q_path, a_path or q_path)
        questions = result.get("questions", [])
        stats = result.get("stats", {})
        
        _parse_jobs[job_id]["status"] = "importing"
        await _save_activity(job_id, status="importing")
        
        created = 0
        skipped = 0
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url:
            try:
                from app.database import AsyncSessionLocal
                from app.models import Question, QuestionVersion
                
                async with AsyncSessionLocal() as db:
                    for q in questions:
                        stem = q.get("stem", "").strip()
                        if not stem or len(stem) < 10:
                            skipped += 1
                            continue
                        
                        section_map = {"rw_m1":"reading_writing","rw_m2":"reading_writing",
                                       "math_m1":"math","math_m2":"math"}
                        section = section_map.get(q.get("section",""), "reading_writing")
                        
                        options = []
                        if q.get("choices"):
                            for c in q["choices"]:
                                options.append({"label": c["label"], "text": c["text"]})
                        
                        question = Question(
                            section=section,
                            type="multiple_choice" if options else "grid_in",
                            status="draft",
                            extraction_confidence=q.get("confidence", 0.85),
                        )
                        db.add(question)
                        await db.flush()
                        
                        version = QuestionVersion(
                            question_id=question.id, version_no=1,
                            stem=stem, passage=q.get("passage"),
                            options=options,
                            correct_answer=q.get("correct_answer", "?"),
                            explanation=None,
                        )
                        db.add(version)
                        await db.flush()
                        question.current_version_id = version.id
                        created += 1
                    await db.commit()
            except Exception as e:
                created = len(questions)
        
        _parse_jobs[job_id] = {
            "status": "done",
            "filename": _parse_jobs[job_id]["filename"],
            "result": {
                "questions_parsed": stats.get("total_questions", len(questions)),
                "answers_matched": stats.get("matched_answers", 0),
                "questions_imported": created,
                "questions_skipped": skipped,
            }
        }
        await _save_activity(job_id, status="done",
            questions_parsed=stats.get("total_questions", len(questions)),
            questions_imported=created, questions_skipped=skipped,
            answers_matched=stats.get("matched_answers", 0))
    except Exception as e:
        _parse_jobs[job_id] = {
            "status": "error",
            "filename": _parse_jobs[job_id]["filename"],
            "error": str(e),
        }
        await _save_activity(job_id, status="error", error=str(e))
    finally:
        try:
            Path(q_path).unlink()
            if a_path:
                Path(a_path).unlink()
        except Exception:
            pass
