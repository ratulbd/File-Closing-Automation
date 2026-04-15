from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from database import engine, Base, get_db
from config import settings
from models import User, UserRole, FileStatus, StepStatus
from schemas import (
    UserCreate, LoginRequest, UserOut, Token, ClearanceFileCreate, ClearanceFileOut,
    ForwardRequest, RejectRequest, DashboardItem
)
from auth import (
    verify_password, create_access_token, get_current_user, require_role, hash_password
)
from crud import (
    create_user, get_user_by_email, create_clearance_file, get_file,
    acknowledge_step, get_current_step, forward_file, reject_file,
    get_dashboard, update_sla_statuses, get_all_files
)
from email_service import send_rejection_alert, send_daily_summary

scheduler = BackgroundScheduler()

def scheduled_sla_update():
    import asyncio
    asyncio.run(run_sla_update())

async def run_sla_update():
    async with AsyncSession(engine) as session:
        await update_sla_statuses(session)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User))
        if not result.scalars().first():
            default_users = [
                ("hr_telecom@ecp.com", "password", UserRole.HR_TELECOM, "HR, Telecom"),
                ("hr_group@ecp.com", "password", UserRole.HR_GROUP, "HR, Group"),
                ("it@ecp.com", "password", UserRole.IT, "IT"),
                ("accounts@ecp.com", "password", UserRole.ACCOUNTS, "Accounts"),
                ("audit@ecp.com", "password", UserRole.AUDIT, "Audit"),
                ("finance@ecp.com", "password", UserRole.FINANCE, "Finance"),
            ]
            for email, pwd, role, dept in default_users:
                session.add(User(email=email, password_hash=hash_password(pwd), role=role, department=dept))
            await session.commit()
    
    scheduler.add_job(scheduled_sla_update, "interval", minutes=5, id="sla_job")
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(title="Employee Clearance Portal", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/auth/register", response_model=UserOut)
async def register(user: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await create_user(db, user)

@app.post("/auth/login", response_model=Token)
async def login(user: LoginRequest, db: AsyncSession = Depends(get_db)):
    db_user = await get_user_by_email(db, user.email)
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(data={"sub": str(db_user.id)})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/files", response_model=ClearanceFileOut)
async def new_file(
    data: ClearanceFileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.HR_TELECOM.value))
):
    return await create_clearance_file(db, data, current_user)

@app.get("/files", response_model=List[ClearanceFileOut])
async def list_files(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_all_files(db)

@app.get("/files/{file_id}", response_model=ClearanceFileOut)
async def file_detail(file_id: int, db: AsyncSession = Depends(get_db)):
    f = await get_file(db, file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return f

@app.post("/files/{file_id}/acknowledge", response_model=ClearanceFileOut)
async def ack_file(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    f = await get_file(db, file_id)
    if not f or f.current_department != current_user.department:
        raise HTTPException(status_code=403, detail="Not authorized")
    step = await get_current_step(db, f.id, f.current_phase, f.current_department)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    await acknowledge_step(db, step)
    await db.refresh(f)
    return f

@app.post("/files/{file_id}/forward", response_model=ClearanceFileOut)
async def fwd_file(
    file_id: int,
    req: ForwardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    f = await get_file(db, file_id)
    if not f or f.current_department != current_user.department:
        raise HTTPException(status_code=403, detail="Not authorized")
    f = await forward_file(db, f, req, current_user)
    return f

@app.post("/files/{file_id}/reject", response_model=ClearanceFileOut)
async def rej_file(
    file_id: int,
    req: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    f = await get_file(db, file_id)
    if not f or f.current_department != current_user.department:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not req.reason or not req.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    f = await reject_file(db, f, req, current_user)
    await send_rejection_alert(f, req.reason, current_user.department)
    return f

@app.get("/dashboard", response_model=List[DashboardItem])
async def dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return await get_dashboard(db, current_user.department)

@app.post("/admin/trigger-daily-summary")
async def trigger_summary(db: AsyncSession = Depends(get_db)):
    await send_daily_summary(db)
    return {"detail": "Summary sent"}
