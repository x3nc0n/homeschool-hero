"""initial backend schema

Revision ID: 20260508_170455
Revises:
Create Date: 2026-05-08T17:04:55.759-05:00
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260508_170455"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

assignment_status = postgresql.ENUM("pending", "complete", "graded", name="assignment_status", create_type=False)
graded_by = postgresql.ENUM("human", "ai", "ai+human", name="graded_by", create_type=False)
grading_job_status = postgresql.ENUM(
    "queued",
    "processing",
    "needs_review",
    "complete",
    "failed",
    name="grading_job_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    assignment_status.create(bind, checkfirst=True)
    graded_by.create(bind, checkfirst=True)
    grading_job_status.create(bind, checkfirst=True)

    op.create_table(
        "students",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_students")),
        sa.UniqueConstraint("name", name=op.f("uq_students_name")),
    )
    op.create_index(op.f("ix_students_id"), "students", ["id"], unique=False)

    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("color", sa.String(length=32), server_default="#4f46e5", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subjects")),
        sa.UniqueConstraint("name", name=op.f("uq_subjects_name")),
    )
    op.create_index(op.f("ix_subjects_id"), "subjects", ["id"], unique=False)

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", assignment_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name=op.f("fk_assignments_subject_id_subjects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assignments")),
    )
    op.create_index(op.f("ix_assignments_id"), "assignments", ["id"], unique=False)
    op.create_index(op.f("ix_assignments_subject_id"), "assignments", ["subject_id"], unique=False)

    op.create_table(
        "quizzes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], name=op.f("fk_quizzes_subject_id_subjects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quizzes")),
    )
    op.create_index(op.f("ix_quizzes_id"), "quizzes", ["id"], unique=False)
    op.create_index(op.f("ix_quizzes_subject_id"), "quizzes", ["subject_id"], unique=False)

    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=255), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["assignment_id"], ["assignments.id"], name=op.f("fk_submissions_assignment_id_assignments"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_submissions_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_submissions")),
    )
    op.create_index(op.f("ix_submissions_id"), "submissions", ["id"], unique=False)
    op.create_index(op.f("ix_submissions_assignment_id"), "submissions", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_submissions_student_id"), "submissions", ["student_id"], unique=False)

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quiz_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["quiz_id"], ["quizzes.id"], name=op.f("fk_quiz_attempts_quiz_id_quizzes"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_quiz_attempts_student_id_students"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quiz_attempts")),
    )
    op.create_index(op.f("ix_quiz_attempts_id"), "quiz_attempts", ["id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_quiz_id"), "quiz_attempts", ["quiz_id"], unique=False)
    op.create_index(op.f("ix_quiz_attempts_student_id"), "quiz_attempts", ["student_id"], unique=False)

    op.create_table(
        "grading_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("status", grading_job_status, nullable=False),
        sa.Column("ocr_result", sa.Text(), nullable=True),
        sa.Column("ai_grade", sa.Float(), nullable=True),
        sa.Column("ai_feedback", sa.Text(), nullable=True),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], name=op.f("fk_grading_jobs_submission_id_submissions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_grading_jobs")),
        sa.UniqueConstraint("submission_id", name=op.f("uq_grading_jobs_submission_id")),
    )
    op.create_index(op.f("ix_grading_jobs_id"), "grading_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_grading_jobs_submission_id"), "grading_jobs", ["submission_id"], unique=False)

    op.create_table(
        "grades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column("letter_grade", sa.String(length=4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("graded_by", graded_by, nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], name=op.f("fk_grades_student_id_students"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], name=op.f("fk_grades_submission_id_submissions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_grades")),
        sa.UniqueConstraint("submission_id", name=op.f("uq_grades_submission_id")),
    )
    op.create_index(op.f("ix_grades_id"), "grades", ["id"], unique=False)
    op.create_index(op.f("ix_grades_submission_id"), "grades", ["submission_id"], unique=False)
    op.create_index(op.f("ix_grades_student_id"), "grades", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_grades_student_id"), table_name="grades")
    op.drop_index(op.f("ix_grades_submission_id"), table_name="grades")
    op.drop_index(op.f("ix_grades_id"), table_name="grades")
    op.drop_table("grades")

    op.drop_index(op.f("ix_grading_jobs_submission_id"), table_name="grading_jobs")
    op.drop_index(op.f("ix_grading_jobs_id"), table_name="grading_jobs")
    op.drop_table("grading_jobs")

    op.drop_index(op.f("ix_quiz_attempts_student_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_quiz_id"), table_name="quiz_attempts")
    op.drop_index(op.f("ix_quiz_attempts_id"), table_name="quiz_attempts")
    op.drop_table("quiz_attempts")

    op.drop_index(op.f("ix_submissions_student_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_assignment_id"), table_name="submissions")
    op.drop_index(op.f("ix_submissions_id"), table_name="submissions")
    op.drop_table("submissions")

    op.drop_index(op.f("ix_quizzes_subject_id"), table_name="quizzes")
    op.drop_index(op.f("ix_quizzes_id"), table_name="quizzes")
    op.drop_table("quizzes")

    op.drop_index(op.f("ix_assignments_subject_id"), table_name="assignments")
    op.drop_index(op.f("ix_assignments_id"), table_name="assignments")
    op.drop_table("assignments")

    op.drop_index(op.f("ix_subjects_id"), table_name="subjects")
    op.drop_table("subjects")

    op.drop_index(op.f("ix_students_id"), table_name="students")
    op.drop_table("students")

    bind = op.get_bind()
    grading_job_status.drop(bind, checkfirst=True)
    graded_by.drop(bind, checkfirst=True)
    assignment_status.drop(bind, checkfirst=True)
