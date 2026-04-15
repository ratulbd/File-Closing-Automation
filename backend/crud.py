from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models import User, ClearanceFile, ClearanceStep, Rejection, UserRole, FileStatus, StepStatus
from schemas import UserCreate, ClearanceFileCreate, ForwardRequest, RejectRequest
from auth import hash_password

# Workflow definition
PHASE_WORKFLOW = {
    1: ["HR_TELECOM", "HR_GROUP", "IT", "ACCOUNTS", "AUDIT"],
    2: ["HR_GROUP", "FINANCE", "AUDIT"],
    3: ["HR_GROUP", "FINANCE"]
}

SLA_HOURS = {
    (1, "HR_TELECOM"): None,
    (1, "HR_GROUP"): 48,
    (1, "IT"): 48,
    (1, "ACCOUNTS"): 72,
    (1, "AUDIT"): 24,
    (2, "HR_GROUP"): 48,
    (2, "FINANCE"): 72,
    (2, "AUDIT"): 24,
    (3, "HR_GROUP"): 24,
    (3, "FINANCE"): 72,
}

async def create_user(db: AsyncSession, user: UserCreate) -> User:
    db_user = User(
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role,
        department=user.department
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def create_clearance_file(db: AsyncSession, data: ClearanceFileCreate, creator: User) -> ClearanceFile:
    file = ClearanceFile(
        employee_id=data.employee_id,
        employee_name=data.employee_name,
        current_phase=1,
        current_department="HR_TELECOM",
        status=FileStatus.PENDING
    )
    db.add(file)
    await db.commit()
    await db.refresh(file)
    # Create first step
    step = ClearanceStep(
        file_id=file.id,
        phase=1,
        department="HR_TELECOM",
        sla_hours=0  # No limit
    )
    db.add(step)
    await db.commit()
    return file

async def get_file(db: AsyncSession, file_id: int) -> Optional[ClearanceFile]:
    result = await db.execute(select(ClearanceFile).where(ClearanceFile.id == file_id))
    return result.scalar_one_or_none()

async def get_files_for_department(db: AsyncSession, department: str, phase: int | None = None):
    q = select(ClearanceFile).where(ClearanceFile.current_department == department)
    if phase is not None:
        q = q.where(ClearanceFile.current_phase == phase)
    q = q.order_by(ClearanceFile.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()

async def get_current_step(db: AsyncSession, file_id: int, phase: int, department: str) -> Optional[ClearanceStep]:
    result = await db.execute(
        select(ClearanceStep)
        .where(ClearanceStep.file_id == file_id)
        .where(ClearanceStep.phase == phase)
        .where(ClearanceStep.department == department)
        .order_by(ClearanceStep.id.desc())
    )
    return result.scalars().first()

async def acknowledge_step(db: AsyncSession, step: ClearanceStep) -> ClearanceStep:
    step.status = StepStatus.ACKNOWLEDGED
    step.acknowledged_at = datetime.utcnow()
    await db.commit()
    await db.refresh(step)
    return step

async def calculate_step_status(step: ClearanceStep) -> StepStatus:
    if step.acknowledged_at is None or step.sla_hours == 0:
        return step.status
    elapsed = datetime.utcnow() - step.acknowledged_at
    sla = timedelta(hours=step.sla_hours)
    near_breach = sla * 0.8
    if elapsed >= sla:
        return StepStatus.BREACHED
    elif elapsed >= near_breach:
        return StepStatus.NEAR_BREACH
    return StepStatus.ACKNOWLEDGED

async def update_sla_statuses(db: AsyncSession):
    result = await db.execute(select(ClearanceStep).where(ClearanceStep.status == StepStatus.ACKNOWLEDGED))
    steps = result.scalars().all()
    for step in steps:
        new_status = await calculate_step_status(step)
        if new_status != step.status:
            step.status = new_status
    await db.commit()

async def forward_file(db: AsyncSession, file: ClearanceFile, request: ForwardRequest, user: User) -> ClearanceFile:
    current_phase = file.current_phase
    current_dept = file.current_department
    
    # Mark current step completed
    step = await get_current_step(db, file.id, current_phase, current_dept)
    if step:
        step.status = StepStatus.COMPLETED
        step.completed_at = datetime.utcnow()
        if request.notes:
            step.notes = request.notes
    
    # Determine next department/phase
    sequence = PHASE_WORKFLOW[current_phase]
    idx = sequence.index(current_dept)
    
    next_dept = None
    next_phase = current_phase
    
    if current_dept == "HR_GROUP" and current_phase == 1 and request.it_required is not None:
        file.it_required = request.it_required
    
    if idx + 1 < len(sequence):
        next_dept = sequence[idx + 1]
        # Skip IT if not required (only in phase 1)
        if current_phase == 1 and next_dept == "IT" and not file.it_required:
            if idx + 2 < len(sequence):
                next_dept = sequence[idx + 2]
            else:
                next_dept = None
    else:
        # Phase complete, move to next phase
        next_phase = current_phase + 1
        if next_phase in PHASE_WORKFLOW:
            next_dept = PHASE_WORKFLOW[next_phase][0]
        else:
            file.status = FileStatus.COMPLETED
            next_dept = None
    
    if next_dept:
        file.current_phase = next_phase
        file.current_department = next_dept
        file.status = FileStatus.IN_PROGRESS
        sla = SLA_HOURS.get((next_phase, next_dept), 24)
        new_step = ClearanceStep(
            file_id=file.id,
            phase=next_phase,
            department=next_dept,
            sla_hours=sla or 0,
            status=StepStatus.PENDING
        )
        db.add(new_step)
    
    await db.commit()
    await db.refresh(file)
    return file

async def reject_file(db: AsyncSession, file: ClearanceFile, request: RejectRequest, user: User) -> ClearanceFile:
    current_phase = file.current_phase
    current_dept = file.current_department
    
    step = await get_current_step(db, file.id, current_phase, current_dept)
    if step:
        # Record rejection
        rejection = Rejection(
            step_id=step.id,
            rejected_by=user.department,
            rejected_to=request.target_department,
            reason=request.reason
        )
        db.add(rejection)
        step.rejection_count += 1
        step.status = StepStatus.COMPLETED  # Close current step
        step.completed_at = datetime.utcnow()
    
    # Move file to target department
    target_phase = None
    for ph, depts in PHASE_WORKFLOW.items():
        if request.target_department in depts:
            target_phase = ph
            break
    
    if target_phase is None:
        raise ValueError("Invalid target department")
    
    file.current_phase = target_phase
    file.current_department = request.target_department
    file.status = FileStatus.REJECTED
    
    sla = SLA_HOURS.get((target_phase, request.target_department), 24)
    new_step = ClearanceStep(
        file_id=file.id,
        phase=target_phase,
        department=request.target_department,
        sla_hours=sla or 0,
        status=StepStatus.PENDING
    )
    db.add(new_step)
    
    await db.commit()
    await db.refresh(file)
    return file

async def get_dashboard(db: AsyncSession, department: str):
    from schemas import DashboardItem
    files = await get_files_for_department(db, department)
    items = []
    for f in files:
        step = await get_current_step(db, f.id, f.current_phase, f.current_department)
        if step:
            await calculate_step_status(step)
            items.append(DashboardItem(
                id=f.id,
                employee_id=f.employee_id,
                employee_name=f.employee_name,
                current_phase=f.current_phase,
                current_department=f.current_department,
                status=f.status,
                step_status=step.status,
                acknowledged_at=step.acknowledged_at,
                sla_hours=step.sla_hours,
                notes=step.notes
            ))
    await db.commit()
    return items

async def get_all_files(db: AsyncSession):
    result = await db.execute(select(ClearanceFile).order_by(ClearanceFile.created_at.desc()))
    return result.scalars().all()
