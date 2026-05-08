from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Assignment, AssignmentStatus, Subject
from backend.schemas.assignments import AssignmentCreate, AssignmentRead, AssignmentStatusUpdate, AssignmentUpdate

router = APIRouter(prefix="/assignments", tags=["assignments"])

_allowed_transitions: dict[AssignmentStatus, set[AssignmentStatus]] = {
    AssignmentStatus.pending: {AssignmentStatus.complete, AssignmentStatus.pending, AssignmentStatus.graded},
    AssignmentStatus.complete: {AssignmentStatus.graded, AssignmentStatus.pending, AssignmentStatus.complete},
    AssignmentStatus.graded: {AssignmentStatus.complete, AssignmentStatus.graded},
}


def _validate_transition(current: AssignmentStatus, nxt: AssignmentStatus) -> None:
    if nxt not in _allowed_transitions[current]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {current.value} to {nxt.value}",
        )


@router.get("", response_model=list[AssignmentRead])
async def list_assignments(db: AsyncSession = Depends(get_db)) -> list[Assignment]:
    result = await db.execute(select(Assignment).order_by(Assignment.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(payload: AssignmentCreate, db: AsyncSession = Depends(get_db)) -> Assignment:
    if not await db.get(Subject, payload.subject_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    assignment = Assignment(**payload.model_dump())
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}", response_model=AssignmentRead)
async def get_assignment(assignment_id: int, db: AsyncSession = Depends(get_db)) -> Assignment:
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return assignment


@router.put("/{assignment_id}", response_model=AssignmentRead)
async def update_assignment(assignment_id: int, payload: AssignmentUpdate, db: AsyncSession = Depends(get_db)) -> Assignment:
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    if not await db.get(Subject, payload.subject_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    _validate_transition(assignment.status, payload.status)
    for key, value in payload.model_dump().items():
        setattr(assignment, key, value)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.patch("/{assignment_id}/status", response_model=AssignmentRead)
async def update_assignment_status(
    assignment_id: int, payload: AssignmentStatusUpdate, db: AsyncSession = Depends(get_db)
) -> Assignment:
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    _validate_transition(assignment.status, payload.status)
    assignment.status = payload.status
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: int, db: AsyncSession = Depends(get_db)) -> None:
    assignment = await db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    await db.delete(assignment)
    await db.commit()
