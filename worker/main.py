"""ARQ worker configuration and parse job handler."""

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings


class WorkerSettings:
    """ARQ worker settings."""
    redis_settings: RedisSettings
    functions: list = []
    
    def __init__(self):
        settings = get_settings()
        self.redis_settings = RedisSettings.from_dsn(settings.redis_url)
        self.functions = [parse_pdf_job]


async def parse_pdf_job(ctx, upload_id: str):
    """Background job: parse an uploaded PDF into draft questions.
    
    This runs in the worker process, isolated from the web tier.
    """
    from app.database import AsyncSessionLocal
    from app.models import Upload, ParseJob

    async with AsyncSessionLocal() as db:
        # Get or create parse job
        from sqlalchemy import select, update
        from datetime import datetime

        job = ParseJob(
            upload_id=upload_id,
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(job)

        # Update upload status
        await db.execute(
            update(Upload).where(Upload.id == upload_id).values(status="parsing")
        )
        await db.commit()

        try:
            # TODO: Phase 2 — integrate OCR parser
            # from worker.parser import PDFParser
            # parser = PDFParser()
            # questions = await parser.parse(upload_id)

            # For now: mark as done
            job.status = "done"
            job.finished_at = datetime.utcnow()
            await db.execute(
                update(Upload).where(Upload.id == upload_id).values(status="parsed")
            )
            await db.commit()

        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.finished_at = datetime.utcnow()
            await db.execute(
                update(Upload).where(Upload.id == upload_id).values(status="failed")
            )
            await db.commit()
            raise
