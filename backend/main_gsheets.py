"""
FastAPI application using Google Sheets as database for Employee Clearance System.
"""
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from config import settings
from models import UserRole, FileStatus, StepStatus
from schemas import (
    UserCreate, LoginRequest, UserOut, Token, ClearanceFileCreate, ClearanceFileOut,
    ForwardRequest, RejectRequest, DashboardItem
)
from auth_gsheets import (
    verify_password, create_access_token, get_current_user, require_role, hash_password
)
from crud_gsheets import GSheetsCRUD
from email_service import send_rejection_alert, send_daily_summary

scheduler = BackgroundScheduler()


def scheduled_sla_update():
    """Scheduled task to update SLA statuses."""
    crud = GSheetsCRUD()
    crud.update_sla_statuses()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for FastAPI app."""
    # Initialize Google Sheets
    try:
        from google_sheets import get_sheets_service
        sheets = get_sheets_service()
        sheets.initialize_spreadsheet()
        print("Google Sheets initialized successfully")

        # Create default users if none exist
        crud = GSheetsCRUD()
        users = crud.sheets.get_rows_with_headers("Users")
        if len(users) == 0:  # Only headers or completely empty
            default_users = [
                ("hr_telecom@ecp.com", "password", UserRole.HR_TELECOM, "HR_TELECOM"),
                ("hr_group@ecp.com", "password", UserRole.HR_GROUP, "HR_GROUP"),
                ("it@ecp.com", "password", UserRole.IT, "IT"),
                ("accounts@ecp.com", "password", UserRole.ACCOUNTS, "ACCOUNTS"),
                ("audit@ecp.com", "password", UserRole.AUDIT, "AUDIT"),
                ("finance@ecp.com", "password", UserRole.FINANCE, "FINANCE"),
            ]
            for email, pwd, role, dept in default_users:
                user_data = UserCreate(email=email, password=pwd, role=role, department=dept)
                crud.create_user(user_data)
            print("Default users created")
    except Exception as e:
        print(f"Error during initialization: {e}")

    scheduler.add_job(scheduled_sla_update, "interval", minutes=5, id="sla_job")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Employee Clearance Portal - Google Sheets", lifespan=lifespan)

# CORS configuration
cors_origins = ["http://localhost:5173", "https://*.firebaseapp.com", "https://*.web.app"]
extra_origins = os.getenv("CORS_ORIGINS", "")
if extra_origins:
    cors_origins = [o.strip() for o in extra_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency for CRUD operations
def get_crud():
    return GSheetsCRUD()


@app.post("/auth/register", response_model=UserOut)
async def register(user: UserCreate, crud: GSheetsCRUD = Depends(get_crud)):
    """Register a new user."""
    existing = crud.get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    created_user = crud.create_user(user)
    return UserOut(
        id=created_user["id"],
        email=created_user["email"],
        role=created_user["role"],
        department=created_user["department"],
        created_at=created_user["created_at"]
    )


@app.post("/auth/login", response_model=Token)
async def login(login_data: LoginRequest, crud: GSheetsCRUD = Depends(get_crud)):
    """Login and get access token."""
    user = crud.get_user_by_email(login_data.email)
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"], "role": user["role"].value},
        expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/auth/me", response_model=UserOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return UserOut(
        id=current_user["id"],
        email=current_user["email"],
        role=current_user["role"],
        department=current_user["department"],
        created_at=current_user["created_at"]
    )


@app.get("/dashboard", response_model=List[DashboardItem])
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    crud: GSheetsCRUD = Depends(get_crud)
):
    """Get dashboard items for current user."""
    items = crud.get_dashboard(current_user)
    return [
        DashboardItem(
            id=item["id"],
            employee_id=item["employee_id"],
            employee_name=item["employee_name"],
            current_phase=item["current_phase"],
            current_department=item["current_department"],
            status=item["status"],
            step_status=item["step_status"],
            acknowledged_at=item["acknowledged_at"],
            sla_hours=item["sla_hours"],
            notes=item.get("notes", "")
        )
        for item in items
    ]


@app.get("/files", response_model=List[ClearanceFileOut])
async def get_files(
    current_user: dict = Depends(get_current_user),
    crud: GSheetsCRUD = Depends(get_crud)
):
    """Get all files (admin only)."""
    if current_user["role"] not in [UserRole.HR_GROUP, UserRole.HR_TELECOM]:
        raise HTTPException(status_code=403, detail="Not authorized")

    files = crud.get_all_files()
    return [
        ClearanceFileOut(
            id=file["id"],
            employee_id=file["employee_id"],
            employee_name=file["employee_name"],
            current_phase=file["current_phase"],
            current_department=file["current_department"],
            status=file["status"],
            it_required=file["it_required"],
            created_at=file["created_at"],
            total_cycle_time=file["total_cycle_time"]
        )
        for file in files
    ]


@app.get("/files/{file_id}", response_model=ClearanceFileOut)
async def get_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    crud: GSheetsCRUD = Depends(get_crud)
):
    """Get a specific file with nested steps and rejections."""
    file = crud.get_file_with_details(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    # Check if user has access to this file
    if file["current_department"] != current_user["department"] and current_user["role"] not in [UserRole.HR_GROUP, UserRole.HR_TELECOM]:
        raise HTTPException(status_code=403, detail="Not authorized to view this file")

    return ClearanceFileOut(**file)


@app.post("/files", response_model=ClearanceFileOut)
async def create_file(
    file_data: ClearanceFileCreate,
    current_user: dict = Depends(require_role(UserRole.HR_TELECOM.value, UserRole.HR_GROUP.value)),
    crud: GSheetsCRUD = Depends(get_crud)
):
    """Create a new clearance file."""
    created_file = crud.create_clearance_file(file_data, current_user)
    return ClearanceFileOut(
        id=created_file["id"],
        employee_id=created_file["employee_id"],
        employee_name=created_file["employee_name"],
        current_phase=created_file["current_phase"],
        current_department=created_file["current_department"],
        status=created_file["status"],
        it_required=created_file["it_required"],
        created_at=created_file["created_at"],
        total_cycle_time=created_file["total_cycle_time"]
    )


@app.post("/files/{file_id}/acknowledge", response_model=ClearanceFileOut)
async def acknowledge_file(
    file_id: str,
    current_user: dict = Depends(get_current_user),
    crud: GSheetsCRUD = Depends(get_crud)
):
    """Acknowledge a file to start SLA timer."""
    file = crud.get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if file["current_department"] != current_user["department"]:
        raise HTTPException(status_code=403, detail="Not authorized to acknowledge this file")

    success = crud.acknowledge_step(file_id, current_user)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to acknowledge file")

    file = crud.get_file_with_details(file_id)
    return ClearanceFileOut(**file)


@app.post("/files/{file_id}/forward", response_model=ClearanceFileOut)
async def forward_file(
    file_id: str,
    forward_data: ForwardRequest,
    current_user: dict = Depends(get_current_user),
    crud: GSheetsCRUD = Depends(get_crud)
):
    """Forward a file to the next department."""
    file = crud.get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if file["current_department"] != current_user["department"]:
        raise HTTPException(status_code=403, detail="Not authorized to forward this file")

    file = crud.forward_file(file_id, forward_data, current_user)
    if not file:
        raise HTTPException(status_code=400, detail="Failed to forward file")

    file = crud.get_file_with_details(file_id)
    return ClearanceFileOut(**file)


@app.post("/files/{file_id}/reject", response_model=ClearanceFileOut)
async def reject_file(
    file_id: str,
    reject_data: RejectRequest,
    current_user: dict = Depends(get_current_user),
    crud: GSheetsCRUD = Depends(get_crud)
):
    """Reject a file back to a previous department."""
    if not reject_data.reason or not reject_data.reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required")

    file = crud.get_file(file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if file["current_department"] != current_user["department"]:
        raise HTTPException(status_code=403, detail="Not authorized to reject this file")

    try:
        file = crud.reject_file(file_id, reject_data, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not file:
        raise HTTPException(status_code=400, detail="Failed to reject file")

    # Send rejection alert email
    try:
        await send_rejection_alert(file, reject_data.reason, current_user["department"])
    except Exception as e:
        print(f"Failed to send rejection email: {e}")

    file = crud.get_file_with_details(file_id)
    return ClearanceFileOut(**file)


@app.post("/admin/trigger-daily-summary")
async def trigger_summary(crud: GSheetsCRUD = Depends(get_crud)):
    """Manually trigger daily summary emails."""
    await send_daily_summary(crud)
    return {"detail": "Summary sent"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "database": "google_sheets"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
