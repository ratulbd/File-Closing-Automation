"""
Google Sheets CRUD operations for Employee Clearance System.
Mirrors the logic of crud.py (SQLite backend) using Google Sheets as storage.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from models import UserRole, FileStatus, StepStatus
from schemas import UserCreate, ClearanceFileCreate, ForwardRequest, RejectRequest
from auth import hash_password, verify_password
from google_sheets import get_sheets_service, WORKSHEETS

# Workflow definition (same as original)
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

VALID_DEPARTMENTS = set()
for depts in PHASE_WORKFLOW.values():
    VALID_DEPARTMENTS.update(depts)


def _generate_id() -> str:
    """Generate a UUID string for primary keys."""
    return str(uuid.uuid4())


class GSheetsCRUD:
    """CRUD operations using Google Sheets."""

    def __init__(self):
        self.sheets = get_sheets_service()

    def _datetime_to_str(self, dt: Optional[datetime]) -> str:
        """Convert datetime to ISO format string for storage."""
        return dt.isoformat() if dt else ""

    def _str_to_datetime(self, s: Optional[str]) -> Optional[datetime]:
        """Convert ISO format string back to datetime."""
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None

    def _parse_int(self, value: Any, default: int = 0) -> int:
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def _parse_bool(self, value: Any) -> bool:
        return str(value).lower() in ("true", "1", "yes", "on")

    # ------------------------------------------------------------------
    # User operations
    # ------------------------------------------------------------------
    def create_user(self, user: UserCreate) -> Dict[str, Any]:
        """Create a new user in Google Sheets."""
        user_id = _generate_id()
        user_data = [
            user_id,
            user.email,
            hash_password(user.password),
            user.role.value,
            user.department,
            self._datetime_to_str(datetime.utcnow())
        ]
        if self.sheets.append_row(WORKSHEETS["users"], user_data):
            return {
                "id": user_id,
                "email": user.email,
                "password_hash": hash_password(user.password),
                "role": user.role,
                "department": user.department,
                "created_at": datetime.utcnow()
            }
        raise Exception("Failed to create user in Google Sheets")

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email from Google Sheets."""
        users = self.sheets.get_rows_with_headers(WORKSHEETS["users"])
        for user in users:
            if user.get("email") == email:
                user["id"] = user.get("id", "")
                user["role"] = UserRole(user["role"]) if user.get("role") else None
                user["created_at"] = self._str_to_datetime(user.get("created_at"))
                return user
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID from Google Sheets."""
        users = self.sheets.get_rows_with_headers(WORKSHEETS["users"])
        for user in users:
            if user.get("id") == user_id:
                user["role"] = UserRole(user["role"]) if user.get("role") else None
                user["created_at"] = self._str_to_datetime(user.get("created_at"))
                return user
        return None

    # ------------------------------------------------------------------
    # Clearance File operations
    # ------------------------------------------------------------------
    def create_clearance_file(self, data: ClearanceFileCreate, creator: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new clearance file in Google Sheets."""
        file_id = _generate_id()
        now = datetime.utcnow()
        file_data = [
            file_id,
            data.employee_id,
            data.employee_name,
            "1",                          # current_phase
            "HR_TELECOM",                 # current_department
            FileStatus.PENDING.value,     # status
            str(data.it_required).lower(),# it_required
            self._datetime_to_str(now),   # created_at
            "0"                           # total_cycle_time
        ]
        if self.sheets.append_row(WORKSHEETS["clearance_files"], file_data):
            # Create ONLY the first step (matches SQLite backend)
            step_id = _generate_id()
            step_data = [
                step_id,
                file_id,
                "1",                       # phase
                "HR_TELECOM",              # department
                "",                        # acknowledged_at
                "",                        # completed_at
                "",                        # sla_hours (no limit)
                StepStatus.PENDING.value,  # status
                "",                        # sla_status
                "",                        # notes
                "0"                        # rejection_count
            ]
            self.sheets.append_row(WORKSHEETS["clearance_steps"], step_data)
            return {
                "id": file_id,
                "employee_id": data.employee_id,
                "employee_name": data.employee_name,
                "current_phase": 1,
                "current_department": "HR_TELECOM",
                "status": FileStatus.PENDING,
                "it_required": data.it_required,
                "created_at": now,
                "total_cycle_time": 0
            }
        raise Exception("Failed to create clearance file in Google Sheets")

    def _file_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "employee_id": row.get("employee_id", ""),
            "employee_name": row.get("employee_name", ""),
            "current_phase": self._parse_int(row.get("current_phase"), 1),
            "current_department": row.get("current_department", ""),
            "status": FileStatus(row.get("status")) if row.get("status") else FileStatus.PENDING,
            "it_required": self._parse_bool(row.get("it_required")),
            "created_at": self._str_to_datetime(row.get("created_at")),
            "total_cycle_time": self._parse_int(row.get("total_cycle_time"), 0),
        }

    def _step_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "file_id": row.get("file_id", ""),
            "phase": self._parse_int(row.get("phase"), 1),
            "department": row.get("department", ""),
            "acknowledged_at": self._str_to_datetime(row.get("acknowledged_at")),
            "completed_at": self._str_to_datetime(row.get("completed_at")),
            "sla_hours": self._parse_int(row.get("sla_hours"), 0),
            "status": StepStatus(row.get("status")) if row.get("status") else StepStatus.PENDING,
            "sla_status": row.get("sla_status") or "PENDING",
            "notes": row.get("notes") or "",
            "rejection_count": self._parse_int(row.get("rejection_count"), 0),
        }

    def _rejection_from_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": row.get("id", ""),
            "step_id": row.get("step_id", ""),
            "rejected_by": row.get("rejected_by", ""),
            "rejected_to": row.get("rejected_to", ""),
            "reason": row.get("reason", ""),
            "rejected_at": self._str_to_datetime(row.get("rejected_at")),
        }

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get clearance file by ID."""
        files = self.sheets.get_rows_with_headers(WORKSHEETS["clearance_files"])
        for file in files:
            if file.get("id") == file_id:
                return self._file_from_row(file)
        return None

    def get_all_files(self) -> List[Dict[str, Any]]:
        """Get all clearance files."""
        files = self.sheets.get_rows_with_headers(WORKSHEETS["clearance_files"])
        result = []
        for file in files:
            if file.get("id"):
                result.append(self._file_from_row(file))
        return result

    def get_files_for_department(self, department: str, phase: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get files for a specific department."""
        files = self.get_all_files()
        result = []
        for f in files:
            if f["current_department"] == department:
                if phase is None or f["current_phase"] == phase:
                    result.append(f)
        return result

    def get_current_step(self, file_id: str, phase: int, department: str) -> Optional[Dict[str, Any]]:
        """Get the most recent step for a file/phase/department combo."""
        steps = self.sheets.get_rows_with_headers(WORKSHEETS["clearance_steps"])
        matches = []
        for step in steps:
            if step.get("file_id") == file_id and self._parse_int(step.get("phase")) == phase and step.get("department") == department:
                matches.append(self._step_from_row(step))
        # Return the most recently created one (last in sheet, or we can just return last match)
        return matches[-1] if matches else None

    def get_steps_for_file(self, file_id: str) -> List[Dict[str, Any]]:
        """Get all steps for a file, ordered by creation (sheet order)."""
        steps = self.sheets.get_rows_with_headers(WORKSHEETS["clearance_steps"])
        result = []
        for step in steps:
            if step.get("file_id") == file_id:
                result.append(self._step_from_row(step))
        return result

    def get_rejections_for_step(self, step_id: str) -> List[Dict[str, Any]]:
        """Get all rejections for a step."""
        rejections = self.sheets.get_rows_with_headers(WORKSHEETS["rejections"])
        result = []
        for r in rejections:
            if r.get("step_id") == step_id:
                result.append(self._rejection_from_row(r))
        return result

    def get_file_with_details(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file with nested steps and rejections (for API parity with SQLite)."""
        file = self.get_file(file_id)
        if not file:
            return None
        steps = self.get_steps_for_file(file_id)
        for step in steps:
            step["rejections"] = self.get_rejections_for_step(step["id"])
        file["steps"] = steps
        return file

    # ------------------------------------------------------------------
    # Step actions
    # ------------------------------------------------------------------
    def acknowledge_step(self, file_id: str, user: Dict[str, Any]) -> bool:
        """Acknowledge the current step for a file."""
        file = self.get_file(file_id)
        if not file:
            return False
        step = self.get_current_step(file_id, file["current_phase"], file["current_department"])
        if not step:
            return False

        step_rows = self.sheets.get_all_rows(WORKSHEETS["clearance_steps"])
        for i, row in enumerate(step_rows):
            if i == 0:
                continue
            if row and row[0] == step["id"]:
                # Update acknowledged_at and status
                # Pad row to required length
                while len(row) < 11:
                    row.append("")
                row[4] = self._datetime_to_str(datetime.utcnow())   # acknowledged_at
                row[7] = StepStatus.ACKNOWLEDGED.value              # status
                return self.sheets.update_row(WORKSHEETS["clearance_steps"], i + 1, row)
        return False

    def _calculate_step_sla_status(self, step: Dict[str, Any]) -> str:
        """Calculate SLA status for a step without mutating it."""
        if not step.get("acknowledged_at") or not step.get("sla_hours"):
            return "PENDING"
        acknowledged = step["acknowledged_at"]
        sla_hours = step["sla_hours"]
        if not isinstance(acknowledged, datetime):
            acknowledged = self._str_to_datetime(str(acknowledged))
        if not acknowledged:
            return "PENDING"
        elapsed = (datetime.utcnow() - acknowledged).total_seconds() / 3600
        if elapsed > sla_hours:
            return "BREACHED"
        elif elapsed > sla_hours * 0.8:
            return "NEAR_BREACH"
        else:
            return "ON_TIME"

    def forward_file(self, file_id: str, data: ForwardRequest, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Forward a file to the next department."""
        file = self.get_file(file_id)
        if not file:
            return None

        current_phase = file["current_phase"]
        current_dept = file["current_department"]

        # Mark current step completed
        step = self.get_current_step(file_id, current_phase, current_dept)
        if step:
            self._update_step_by_id(
                step["id"],
                status=StepStatus.COMPLETED.value,
                completed_at=self._datetime_to_str(datetime.utcnow()),
                notes=data.notes if data.notes else step.get("notes", "")
            )

        # Determine next department/phase
        sequence = PHASE_WORKFLOW[current_phase]
        idx = sequence.index(current_dept) if current_dept in sequence else -1

        next_dept = None
        next_phase = current_phase

        if current_dept == "HR_GROUP" and current_phase == 1 and data.it_required is not None:
            # Update it_required on file
            self._update_file_field(file_id, "it_required", str(data.it_required).lower())
            file["it_required"] = data.it_required

        if idx + 1 < len(sequence):
            next_dept = sequence[idx + 1]
            if current_phase == 1 and next_dept == "IT" and not file["it_required"]:
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
                # All phases complete
                self._update_file_fields(file_id, {
                    "status": FileStatus.COMPLETED.value,
                })
                file["status"] = FileStatus.COMPLETED
                return file

        if next_dept:
            sla = SLA_HOURS.get((next_phase, next_dept), 24)
            new_step_id = _generate_id()
            step_data = [
                new_step_id,
                file_id,
                str(next_phase),
                next_dept,
                "",                       # acknowledged_at
                "",                       # completed_at
                str(sla) if sla else "",  # sla_hours
                StepStatus.PENDING.value, # status
                "",                       # sla_status
                "",                       # notes
                "0"                       # rejection_count
            ]
            self.sheets.append_row(WORKSHEETS["clearance_steps"], step_data)
            self._update_file_fields(file_id, {
                "current_phase": str(next_phase),
                "current_department": next_dept,
                "status": FileStatus.IN_PROGRESS.value,
            })
            file["current_phase"] = next_phase
            file["current_department"] = next_dept
            file["status"] = FileStatus.IN_PROGRESS

        return file

    def reject_file(self, file_id: str, data: RejectRequest, user: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Reject a file back to a previous department."""
        file = self.get_file(file_id)
        if not file:
            return None

        current_phase = file["current_phase"]
        current_dept = file["current_department"]

        step = self.get_current_step(file_id, current_phase, current_dept)
        if not step:
            return None

        # Record rejection
        rejection_id = _generate_id()
        rejection_data = [
            rejection_id,
            step["id"],
            user["department"],
            data.target_department,
            data.reason,
            self._datetime_to_str(datetime.utcnow())
        ]
        self.sheets.append_row(WORKSHEETS["rejections"], rejection_data)

        # Mark current step completed
        self._update_step_by_id(
            step["id"],
            status=StepStatus.COMPLETED.value,
            completed_at=self._datetime_to_str(datetime.utcnow()),
            rejection_count=str(step.get("rejection_count", 0) + 1)
        )

        # Resolve target phase
        target_phase = None
        for ph, depts in PHASE_WORKFLOW.items():
            if data.target_department in depts:
                target_phase = ph
                break

        if target_phase is None or data.target_department not in VALID_DEPARTMENTS:
            raise ValueError("Invalid target department")

        # Create new step for target department
        sla = SLA_HOURS.get((target_phase, data.target_department), 24)
        new_step_id = _generate_id()
        step_data = [
            new_step_id,
            file_id,
            str(target_phase),
            data.target_department,
            "",                       # acknowledged_at
            "",                       # completed_at
            str(sla) if sla else "",  # sla_hours
            StepStatus.PENDING.value, # status
            "",                       # sla_status
            "",                       # notes
            "0"                       # rejection_count
        ]
        self.sheets.append_row(WORKSHEETS["clearance_steps"], step_data)

        self._update_file_fields(file_id, {
            "current_phase": str(target_phase),
            "current_department": data.target_department,
            "status": FileStatus.REJECTED.value,
        })
        file["current_phase"] = target_phase
        file["current_department"] = data.target_department
        file["status"] = FileStatus.REJECTED
        return file

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _update_step_by_id(self, step_id: str, **kwargs) -> bool:
        """Update specific fields of a step by its ID."""
        step_rows = self.sheets.get_all_rows(WORKSHEETS["clearance_steps"])
        headers = step_rows[0] if step_rows else []
        for i, row in enumerate(step_rows):
            if i == 0:
                continue
            if row and row[0] == step_id:
                # Ensure row has enough columns
                while len(row) < len(headers):
                    row.append("")
                for key, value in kwargs.items():
                    if key in headers:
                        row[headers.index(key)] = value
                return self.sheets.update_row(WORKSHEETS["clearance_steps"], i + 1, row)
        return False

    def _update_file_field(self, file_id: str, field: str, value: str) -> bool:
        return self._update_file_fields(file_id, {field: value})

    def _update_file_fields(self, file_id: str, updates: Dict[str, str]) -> bool:
        """Update specific fields of a file by its ID."""
        file_rows = self.sheets.get_all_rows(WORKSHEETS["clearance_files"])
        headers = file_rows[0] if file_rows else []
        for i, row in enumerate(file_rows):
            if i == 0:
                continue
            if row and row[0] == file_id:
                while len(row) < len(headers):
                    row.append("")
                for key, value in updates.items():
                    if key in headers:
                        row[headers.index(key)] = value
                return self.sheets.update_row(WORKSHEETS["clearance_files"], i + 1, row)
        return False

    # ------------------------------------------------------------------
    # Dashboard & SLA
    # ------------------------------------------------------------------
    def get_dashboard(self, user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get dashboard items for a user."""
        files = self.get_files_for_department(user["department"])
        dashboard = []
        for file in files:
            step = self.get_current_step(file["id"], file["current_phase"], file["current_department"])
            if step:
                sla_status = self._calculate_step_sla_status(step)
                # Map SLA status to frontend-friendly step status
                if step["status"] == StepStatus.ACKNOWLEDGED.value:
                    if sla_status == "BREACHED":
                        step_status_display = StepStatus.BREACHED.value
                    elif sla_status == "NEAR_BREACH":
                        step_status_display = StepStatus.NEAR_BREACH.value
                    else:
                        step_status_display = StepStatus.ACKNOWLEDGED.value
                else:
                    step_status_display = step["status"].value if hasattr(step["status"], "value") else step["status"]

                dashboard.append({
                    "id": file["id"],
                    "employee_id": file["employee_id"],
                    "employee_name": file["employee_name"],
                    "current_phase": file["current_phase"],
                    "current_department": file["current_department"],
                    "status": file["status"],
                    "step_status": step_status_display,
                    "acknowledged_at": step["acknowledged_at"],
                    "sla_hours": step["sla_hours"] or 0,
                    "notes": step.get("notes", "") or ""
                })
        return dashboard

    def update_sla_statuses(self):
        """Update SLA statuses for all steps (called by scheduler)."""
        steps = self.sheets.get_rows_with_headers(WORKSHEETS["clearance_steps"])
        headers = ["id", "file_id", "phase", "department", "acknowledged_at", "completed_at",
                   "sla_hours", "status", "sla_status", "notes", "rejection_count"]
        updates = []
        for step_dict in steps:
            step = self._step_from_row(step_dict)
            if step.get("status") == StepStatus.ACKNOWLEDGED.value and step.get("sla_hours"):
                sla_status = self._calculate_step_sla_status(step)
                current_sla_status = step.get("sla_status") or ""
                if sla_status != current_sla_status:
                    # Find row index
                    step_rows = self.sheets.get_all_rows(WORKSHEETS["clearance_steps"])
                    for i, row in enumerate(step_rows):
                        if i == 0:
                            continue
                        if row and row[0] == step["id"]:
                            while len(row) < len(headers):
                                row.append("")
                            row[8] = sla_status  # sla_status column
                            updates.append((i + 1, row))
                            break
        if updates:
            self.sheets.batch_update_rows(WORKSHEETS["clearance_steps"], updates)
