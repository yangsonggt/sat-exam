#!/usr/bin/env python3
"""Import OCR-parsed SAT questions into the database.

Usage:
  python scripts/import_questions.py <question_pdf> <answer_pdf> [--fix-math]
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent to path so we can import ocr_parser
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".."))
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.models import Question, QuestionVersion, User
from sqlalchemy import select

# Import ocr_parser from the parent project
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ocr_parser import OCRParser


async def import_questions(q_pdf: str, a_pdf: str, uploader_email: str = "admin@sat-exam.com",
                           fix_math: bool = False):
    """Parse PDFs and import questions into the database."""
    
    # 1. Parse PDFs
    print(f"Parsing {Path(q_pdf).name}...")
    parser = OCRParser(dpi=200)
    result = parser.parse_full_document(q_pdf, a_pdf)

    stats = result["stats"]
    print(f"  Extracted: {stats['total_questions']} questions")
    print(f"  Matched answers: {stats['matched_answers']}")
    print(f"  Unmatched: {stats['unmatched_answers']}")

    # 2. Fix math via DeepSeek if requested
    if fix_math:
        print("\nFixing math notation via DeepSeek...")
        from fix_math_llm import fix_math_batch, has_math, is_math_garbled, load_env
        load_env()
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

        if api_key:
            math_qs = [q for q in result["questions"]
                       if q.get("section", "").startswith("math")
                       and has_math(q["stem"]) and is_math_garbled(q["stem"])]
            print(f"  Found {len(math_qs)} math questions to fix")

            for i, q in enumerate(math_qs):
                print(f"  [{i+1}/{len(math_qs)}] Q{q['number']}...", end=" ", flush=True)
                try:
                    fix_math_batch([q], api_key=api_key, base_url=base_url)
                    print("OK")
                except Exception as e:
                    print(f"ERROR: {e}")
        else:
            print("  Skipped: DEEPSEEK_API_KEY not set")

    # 3. Import into database
    print("\nImporting into database...")
    async with AsyncSessionLocal() as db:
        # Get uploader user
        r = await db.execute(select(User).where(User.email == uploader_email))
        uploader = r.scalar_one_or_none()
        if not uploader:
            print(f"ERROR: User '{uploader_email}' not found. Run run.sh first.")
            return

        created = 0
        skipped = 0

        for q in result["questions"]:
            stem = q.get("stem", "").strip()
            if not stem or len(stem) < 10:
                skipped += 1
                continue

            # Map section
            section_map = {
                "rw_m1": "reading_writing",
                "rw_m2": "reading_writing",
                "math_m1": "math",
                "math_m2": "math",
            }
            section = section_map.get(q.get("section", ""), "reading_writing")

            # Build options
            options = []
            if q.get("choices"):
                for c in q["choices"]:
                    options.append({"label": c["label"], "text": c["text"]})
            q_type = "multiple_choice" if options else "grid_in"

            # Create question
            question = Question(
                section=section,
                type=q_type,
                skill=None,  # Editor assigns during review
                difficulty=None,  # Editor assigns during review
                status="draft",
                extraction_confidence=q.get("confidence", 0.8),
            )
            db.add(question)
            await db.flush()

            # Create version
            correct_answer = q.get("correct_answer", "")
            if not correct_answer:
                correct_answer = "?"  # Placeholder for unmatched

            version = QuestionVersion(
                question_id=question.id,
                version_no=1,
                stem=stem,
                passage=q.get("passage"),
                options=options,
                correct_answer=correct_answer,
                explanation=None,
            )
            db.add(version)
            await db.flush()

            question.current_version_id = version.id
            created += 1

        await db.commit()
        print(f"  Created: {created} questions")
        print(f"  Skipped: {skipped} (empty/too-short stems)")
        print(f"\nQuestions imported as DRAFTS. Use the review UI to:")
        print(f"  1. Verify stems and answers")
        print(f"  2. Assign skill/domain from the controlled vocabulary")
        print(f"  3. Set difficulty (easy/medium/hard)")
        print(f"  4. Publish (POST /api/v1/questions/{{id}}/publish)")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    q_pdf = sys.argv[1]
    a_pdf = sys.argv[2]
    fix_math = "--fix-math" in sys.argv

    asyncio.run(import_questions(q_pdf, a_pdf, fix_math=fix_math))


if __name__ == "__main__":
    main()
