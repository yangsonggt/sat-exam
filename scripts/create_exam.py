#!/usr/bin/env python3
"""Create and publish a Digital SAT exam from the question pool."""

import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import AsyncSessionLocal
from app.models import Exam, ExamModule, ExamSelectionRule
from app.exam.service import validate_publish, publish_exam
from sqlalchemy import text
from sqlalchemy.orm import selectinload
from sqlalchemy import select


async def main():
    async with AsyncSessionLocal() as db:
        r = await db.execute(text("SELECT id FROM users WHERE email='admin@sat-exam.com' LIMIT 1"))
        admin_id = r.scalar()

        exam = Exam(title="Digital SAT Practice Test 1 (Dec 2023)",
                    description="Full-length Digital SAT with section-adaptive modules.",
                    routing_threshold_rw=14, routing_threshold_math=11,
                    timer_mode="strict", status="draft", created_by=admin_id)
        db.add(exam)
        await db.flush()

        # === R&W: 27 Q per module ===
        rw_skills = [
            "rw.craft_structure.words_in_context",
            "rw.craft_structure.text_structure_purpose",
            "rw.craft_structure.cross_text_connections",
            "rw.information_ideas.central_ideas_details",
            "rw.information_ideas.command_of_evidence_textual",
            "rw.information_ideas.command_of_evidence_quantitative",
            "rw.information_ideas.inferences",
            "rw.standard_english_conventions.boundaries",
            "rw.standard_english_conventions.form_structure_sense",
            "rw.expression_of_ideas.rhetorical_synthesis",
            "rw.expression_of_ideas.transitions",
        ]
        rw_rules = [(s, 1) for s in rw_skills]  # 11 base
        rw_rules += [(rw_skills[i % 11], 1) for i in range(16)]  # 16 more = 27 total

        for form in ["base", "easier", "harder"]:
            m = ExamModule(exam_id=exam.id, section="reading_writing",
                           module_no=1 if form == "base" else 2, form=form,
                           time_limit_min=32, question_count=27)
            db.add(m)
            await db.flush()
            for skill, count in rw_rules:
                db.add(ExamSelectionRule(exam_module_id=m.id, skill=skill, count=count))

        # === Math: 22 Q per module ===
        math_skills = [
            "math.algebra.linear_equations_one_variable",
            "math.algebra.linear_equations_two_variables",
            "math.algebra.linear_functions",
            "math.algebra.systems_two_linear_equations",
            "math.algebra.linear_inequalities",
            "math.advanced_math.equivalent_expressions",
            "math.advanced_math.nonlinear_equations_systems",
            "math.advanced_math.nonlinear_functions",
            "math.problem_solving_data.ratios_rates_proportions_units",
            "math.problem_solving_data.percentages",
            "math.problem_solving_data.one_variable_data",
            "math.problem_solving_data.two_variable_data",
            "math.problem_solving_data.probability",
            "math.problem_solving_data.sample_statistics_moe",
            "math.problem_solving_data.evaluating_statistical_claims",
            "math.geometry_trigonometry.area_volume",
            "math.geometry_trigonometry.lines_angles_triangles",
            "math.geometry_trigonometry.right_triangles_trig",
            "math.geometry_trigonometry.circles",
        ]
        math_rules = [(s, 1) for s in math_skills]  # 19 base
        math_rules += [(math_skills[i % 19], 1) for i in range(3)]  # 3 more = 22 total

        for form in ["base", "easier", "harder"]:
            m = ExamModule(exam_id=exam.id, section="math",
                           module_no=1 if form == "base" else 2, form=form,
                           time_limit_min=35, question_count=22)
            db.add(m)
            await db.flush()
            for skill, count in math_rules:
                db.add(ExamSelectionRule(exam_module_id=m.id, skill=skill, count=count))

        await db.commit()
        print(f"Exam created: {exam.id}")

        # Validate
        errors = await validate_publish(db, exam.id)
        if errors:
            print(f"Validation: {len(errors)} gaps (will skip missing skills)")
        else:
            print("Validation: ALL RULES SATISFIED")

        # Publish (skips rules with 0 available)
        try:
            exam = await publish_exam(db, exam.id)
            print(f"\nPUBLISHED: {exam.title}")
            for m in exam.modules:
                print(f"  {m.section} M{m.module_no} ({m.form}): {m.question_count}Q, {m.time_limit_min}min")
        except Exception as e:
            # Adjust rules to match reality
            print(f"\nAdjusting rules to match available pool...")
            for m in exam.modules:
                for rule in m.selection_rules:
                    r = await db.execute(text(
                        "SELECT count(*) FROM questions WHERE status='published' AND section=:sec"
                        + (" AND skill=:sk" if rule.skill else ""),
                        {"sec": m.section, "sk": rule.skill} if rule.skill else {"sec": m.section}
                    ))
                    available = r.scalar()
                    rule.count = min(rule.count, max(1, available))
            await db.commit()
            exam = await publish_exam(db, exam.id)
            print(f"PUBLISHED with adjusted counts: {exam.title}")


if __name__ == "__main__":
    asyncio.run(main())
