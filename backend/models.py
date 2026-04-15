import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from database import Base

class UserRole(str, enum.Enum):
    HR_TELECOM = "HR_TELECOM"
    HR_GROUP = "HR_GROUP"
    IT = "IT"
    ACCOUNTS = "ACCOUNTS"
    AUDIT = "AUDIT"
    FINANCE = "FINANCE"

class FileStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

class StepStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    COMPLETED = "COMPLETED"
    BREACHED = "BREACHED"
    NEAR_BREACH = "NEAR_BREACH"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    department = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class ClearanceFile(Base):
    __tablename__ = "clearance_files"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, nullable=False)
    employee_name = Column(String, nullable=False)
    current_phase = Column(Integer, default=1)
    current_department = Column(String, nullable=False)
    status = Column(SQLEnum(FileStatus), default=FileStatus.PENDING)
    it_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_cycle_time = Column(Integer, default=0)  # in minutes

    steps = relationship("ClearanceStep", back_populates="file", order_by="ClearanceStep.id", lazy="selectin")

class ClearanceStep(Base):
    __tablename__ = "clearance_steps"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("clearance_files.id"), nullable=False)
    phase = Column(Integer, nullable=False)
    department = Column(String, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    sla_hours = Column(Integer, nullable=False)
    status = Column(SQLEnum(StepStatus), default=StepStatus.PENDING)
    notes = Column(Text, nullable=True)
    rejection_count = Column(Integer, default=0)

    file = relationship("ClearanceFile", back_populates="steps")
    rejections = relationship("Rejection", back_populates="step", order_by="Rejection.id", lazy="selectin")

class Rejection(Base):
    __tablename__ = "rejections"
    id = Column(Integer, primary_key=True, index=True)
    step_id = Column(Integer, ForeignKey("clearance_steps.id"), nullable=False)
    rejected_by = Column(String, nullable=False)
    rejected_to = Column(String, nullable=False)
    reason = Column(Text, nullable=False)
    rejected_at = Column(DateTime, default=datetime.utcnow)

    step = relationship("ClearanceStep", back_populates="rejections")
