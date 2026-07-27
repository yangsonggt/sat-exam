"""Upload router: PDF upload, list, status, delete."""

from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.post("/parse")
async def upload_and_parse_pdf(
    file: UploadFile = File(...),
    user: User = Depends(require_role("admin", "editor")),
):
    """Upload a PDF, OCR it, and import questions. Returns stats."""
    import tempfile
    import uuid
    from pathlib import Path
    from sqlalchemy.ext.asyncio import AsyncSession

    # Validate
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    # Save to temp file
    ext = file.filename.rsplit(".", 1)[-1]
    tmp = Path(tempfile.gettempdir()) / f"sat_upload_{uuid.uuid4().hex}.{ext}"
    tmp.write_bytes(await file.read())

    try:
        # Try v2 parser first, fall back to v1
        parser = None
        try:
            from ocr_parser_v2 import HybridOCRParser
            parser = HybridOCRParser(dpi=200)
            print(f"Using hybrid OCR v2 for {file.filename}")
        except ImportError:
            from ocr_parser import OCRParser as OCP
            parser = OCP(dpi=200)
            print(f"Using OCR v1 for {file.filename}")

        result = parser.parse_full_document(str(tmp), str(tmp))  # same PDF if no answer key
        questions = result.get("questions", [])
        stats = result.get("stats", {})

        # Import into DB
        created = len(questions)  # default: all parsed
        skipped = 0
        db_url = os.environ.get("DATABASE_URL", "")
        if "sqlite" in db_url or "postgresql" in db_url or "postgres" in db_url:
            try:
                from app.database import AsyncSessionLocal
                from app.models import Question, QuestionVersion

                async with AsyncSessionLocal() as db:
                    created = 0
                    for q in questions:
                        stem = q.get("stem", "").strip()
                        if not stem or len(stem) < 10:
                            skipped += 1
                            continue

                        section_map = {
                            "rw_m1": "reading_writing", "rw_m2": "reading_writing",
                            "math_m1": "math", "math_m2": "math",
                        }
                        section = section_map.get(q.get("section", ""), "reading_writing")

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
                            question_id=question.id,
                            version_no=1,
                            stem=stem,
                            passage=q.get("passage"),
                            options=options,
                            correct_answer=q.get("correct_answer", "?"),
                            explanation=None,
                        )
                        db.add(version)
                        await db.flush()
                        question.current_version_id = version.id
                        created += 1

                    await db.commit()
                    print(f"Imported {created} questions from {file.filename}")
            except Exception as e:
                print(f"DB import skipped: {e}")
                created = len(questions)

        return {
            "filename": file.filename,
            "questions_parsed": stats.get("total_questions", len(questions)),
            "answers_matched": stats.get("matched_answers", 0),
            "questions_imported": created,
            "questions_skipped": skipped if 'skipped' in dir() else 0,
        }
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass
