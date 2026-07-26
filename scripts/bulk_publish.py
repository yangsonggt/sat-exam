#!/usr/bin/env python3
"""Bulk-tag and publish all draft questions in the database.

Uses DeepSeek LLM to classify each question by skill + difficulty,
then publishes them.
"""

import asyncio
import json
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import Question, QuestionVersion, SkillVocabulary
from sqlalchemy import text, select


def load_env():
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key.strip()] = val.strip().strip('"').strip("'")


async def get_vocabulary(db):
    """Get available skills grouped by section."""
    result = await db.execute(
        select(SkillVocabulary).order_by(SkillVocabulary.display_order)
    )
    skills = result.scalars().all()
    vocab = {}
    for s in skills:
        vocab[s.skill_key] = {"section": s.section, "label": s.skill_label}
    return vocab


def classify_question(stem: str, section: str, vocab: dict) -> tuple:
    """Use DeepSeek to classify a question's skill and difficulty."""
    load_env()
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    if not api_key:
        return None, "medium"

    # Build skill list for this section
    section_skills = {k: v for k, v in vocab.items() if v["section"] == section}
    skill_list = "\n".join(f"  {k}: {v['label']}" for k, v in section_skills.items())

    prompt = f"""Classify this SAT question. Return ONLY a JSON object with two fields:
- "skill": one of the skill keys below
- "difficulty": "easy", "medium", or "hard"

Available skills for {section}:
{skill_list}

Question stem:
{stem[:500]}

Return: {{"skill": "...", "difficulty": "..."}}"""

    payload = json.dumps({
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 100,
        "temperature": 0,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        result = json.loads(content)
        skill = result.get("skill", "")
        difficulty = result.get("difficulty", "medium")
        # Validate skill exists in vocabulary
        if skill not in vocab:
            # Default to first skill in section
            for k, v in vocab.items():
                if v["section"] == section:
                    skill = k
                    break
        return skill, difficulty
    except Exception as e:
        print(f"    LLM error: {e}")
        return None, "medium"


async def bulk_publish(use_llm: bool = False):
    """Tag and publish all draft questions."""
    load_env()

    async with AsyncSessionLocal() as db:
        # Get vocabulary
        vocab = await get_vocabulary(db)
        print(f"Loaded {len(vocab)} skills from vocabulary")

        # Get all draft questions with their versions
        result = await db.execute(
            select(Question).where(Question.status == "draft")
        )
        questions = list(result.scalars().all())
        print(f"Found {len(questions)} draft questions\n")

        # Default skills per section (fallback if LLM disabled)
        defaults = {
            "reading_writing": "rw.craft_structure.words_in_context",
            "math": "math.algebra.linear_equations_one_variable",
        }

        tagged = 0
        for i, q in enumerate(questions):
            # Get stem
            vresult = await db.execute(
                select(QuestionVersion).where(QuestionVersion.id == q.current_version_id)
            )
            version = vresult.scalar_one_or_none()
            if not version:
                continue

            stem = version.stem

            if use_llm:
                skill, difficulty = classify_question(stem, q.section, vocab)
            else:
                # Round-robin skills per section
                section_skills = [k for k, v in vocab.items() if v["section"] == q.section]
                skill = section_skills[tagged % len(section_skills)] if section_skills else defaults.get(q.section, "")
                difficulties = ["easy", "medium", "hard"]
                difficulty = difficulties[tagged % 3]

            if skill is None:
                skill = defaults.get(q.section, "")

            q.skill = skill
            q.difficulty = difficulty
            q.status = "published"
            tagged += 1

            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{len(questions)} tagged...")

        await db.commit()
        print(f"\nPublished {tagged}/{len(questions)} questions")

        # Verify
        result = await db.execute(
            select(Question).where(Question.status == "published")
        )
        published = list(result.scalars().all())
        print(f"Verified: {len(published)} published questions")

        # Show distribution
        result = await db.execute(text(
            "SELECT section, skill, difficulty, count(*) FROM questions "
            "WHERE status='published' "
            "GROUP BY section, skill, difficulty ORDER BY section, skill, difficulty"
        ))
        print("\nDistribution:")
        for row in result:
            print(f"  {row[0]:20s} {row[3]:3d} questions | {row[1]:50s} | {row[2]}")


def main():
    use_llm = "--llm" in sys.argv
    asyncio.run(bulk_publish(use_llm=use_llm))


if __name__ == "__main__":
    main()
