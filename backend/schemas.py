from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from models import UserRole, FileStatus, StepStatus

# User schemas
class UserCreate(BaseModel):
    email: str
    password: str
    role: UserRole
    department: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    role: UserRole
    department: str
    created_at: datetime
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

# Rejection schemas
class RejectionCreate(BaseModel):
    rejected_by: str
    rejected_to: str
    reason: str

class RejectionOut(BaseModel):
    id: str
    rejected_by: str
    rejected_to: str
    reason: str
    rejected_at: datetime
    class Config:
        from_attributes = True

# Step schemas
class ClearanceStepOut(BaseModel):
    id: str
    phase: int
    department: str
    acknowledged_at: Optional[datetime]
    completed_at: Optional[datetime]
    sla_hours: int
    status: StepStatus
    notes: Optional[str]
    rejection_count: int
    rejections: List[RejectionOut] = []
    class Config:
        from_attributes = True

# File schemas
class ClearanceFileCreate(BaseModel):
    employee_id: str
    employee_name: str
    department: str
    clearance_reason: str
    it_required: bool = False

class ClearanceFileOut(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    current_phase: int
    current_department: str
    status: FileStatus
    it_required: bool
    created_at: datetime
    total_cycle_time: int
    steps: List[ClearanceStepOut] = []
    class Config:
        from_attributes = True

class ForwardRequest(BaseModel):
    it_required: Optional[bool] = None
    notes: Optional[str] = None

class RejectRequest(BaseModel):
    reason: str
    target_department: str

# Dashboard
class DashboardItem(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    current_phase: int
    current_department: str
    status: FileStatus
    step_status: StepStatus
    acknowledged_at: Optional[datetime]
    sla_hours: int
    notes: Optional[str]
