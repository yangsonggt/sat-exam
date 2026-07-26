"""Seed the skill_vocabulary table with Digital SAT domains and skills."""

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import SkillVocabulary

SKILLS = [
    # Reading & Writing
    ("reading_writing", "rw.craft_structure", "Craft and Structure",
     "rw.craft_structure.words_in_context", "Words in Context", 1),
    ("reading_writing", "rw.craft_structure", "Craft and Structure",
     "rw.craft_structure.text_structure_purpose", "Text Structure and Purpose", 2),
    ("reading_writing", "rw.craft_structure", "Craft and Structure",
     "rw.craft_structure.cross_text_connections", "Cross-Text Connections", 3),
    ("reading_writing", "rw.information_ideas", "Information and Ideas",
     "rw.information_ideas.central_ideas_details", "Central Ideas and Details", 4),
    ("reading_writing", "rw.information_ideas", "Information and Ideas",
     "rw.information_ideas.command_of_evidence_textual", "Command of Evidence — Textual", 5),
    ("reading_writing", "rw.information_ideas", "Information and Ideas",
     "rw.information_ideas.command_of_evidence_quantitative", "Command of Evidence — Quantitative", 6),
    ("reading_writing", "rw.information_ideas", "Information and Ideas",
     "rw.information_ideas.inferences", "Inferences", 7),
    ("reading_writing", "rw.standard_english_conventions", "Standard English Conventions",
     "rw.standard_english_conventions.boundaries", "Boundaries", 8),
    ("reading_writing", "rw.standard_english_conventions", "Standard English Conventions",
     "rw.standard_english_conventions.form_structure_sense", "Form, Structure, and Sense", 9),
    ("reading_writing", "rw.expression_of_ideas", "Expression of Ideas",
     "rw.expression_of_ideas.rhetorical_synthesis", "Rhetorical Synthesis", 10),
    ("reading_writing", "rw.expression_of_ideas", "Expression of Ideas",
     "rw.expression_of_ideas.transitions", "Transitions", 11),

    # Math
    ("math", "math.algebra", "Algebra",
     "math.algebra.linear_equations_one_variable", "Linear equations in one variable", 12),
    ("math", "math.algebra", "Algebra",
     "math.algebra.linear_equations_two_variables", "Linear equations in two variables", 13),
    ("math", "math.algebra", "Algebra",
     "math.algebra.linear_functions", "Linear functions", 14),
    ("math", "math.algebra", "Algebra",
     "math.algebra.systems_two_linear_equations", "Systems of two linear equations", 15),
    ("math", "math.algebra", "Algebra",
     "math.algebra.linear_inequalities", "Linear inequalities", 16),
    ("math", "math.advanced_math", "Advanced Math",
     "math.advanced_math.equivalent_expressions", "Equivalent expressions", 17),
    ("math", "math.advanced_math", "Advanced Math",
     "math.advanced_math.nonlinear_equations_systems", "Nonlinear equations & systems", 18),
    ("math", "math.advanced_math", "Advanced Math",
     "math.advanced_math.nonlinear_functions", "Nonlinear functions", 19),
    ("math", "math.problem_solving_data", "Problem-Solving and Data Analysis",
     "math.problem_solving_data.ratios_rates_proportions_units", "Ratios, rates, proportions, units", 20),
    ("math", "math.problem_solving_data", "Problem-Solving and Data Analysis",
     "math.problem_solving_data.percentages", "Percentages", 21),
    ("math", "math.problem_solving_data", "Problem-Solving and Data Analysis",
     "math.problem_solving_data.one_variable_data", "One-variable data", 22),
    ("math", "math.problem_solving_data", "Problem-Solving and Data Analysis",
     "math.problem_solving_data.two_variable_data", "Two-variable data", 23),
    ("math", "math.problem_solving_data", "Problem-Solving and Data Analysis",
     "math.problem_solving_data.probability", "Probability", 24),
    ("math", "math.problem_solving_data", "Problem-Solving and Data Analysis",
     "math.problem_solving_data.sample_statistics_moe", "Sample statistics & margin of error", 25),
    ("math", "math.problem_solving_data", "Problem-Solving and Data Analysis",
     "math.problem_solving_data.evaluating_statistical_claims", "Evaluating statistical claims", 26),
    ("math", "math.geometry_trigonometry", "Geometry and Trigonometry",
     "math.geometry_trigonometry.area_volume", "Area and volume", 27),
    ("math", "math.geometry_trigonometry", "Geometry and Trigonometry",
     "math.geometry_trigonometry.lines_angles_triangles", "Lines, angles, and triangles", 28),
    ("math", "math.geometry_trigonometry", "Geometry and Trigonometry",
     "math.geometry_trigonometry.right_triangles_trig", "Right triangles and trigonometry", 29),
    ("math", "math.geometry_trigonometry", "Geometry and Trigonometry",
     "math.geometry_trigonometry.circles", "Circles", 30),
]


async def seed_skills():
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        result = await db.execute(select(SkillVocabulary).limit(1))
        if result.scalar_one_or_none():
            print("Skill vocabulary already seeded, skipping.")
            return

        for section, domain_key, domain_label, skill_key, skill_label, order in SKILLS:
            db.add(SkillVocabulary(
                section=section,
                domain_key=domain_key,
                domain_label=domain_label,
                skill_key=skill_key,
                skill_label=skill_label,
                display_order=order,
            ))

        await db.commit()
        print(f"Seeded {len(SKILLS)} skills into skill_vocabulary.")


if __name__ == "__main__":
    asyncio.run(seed_skills())
