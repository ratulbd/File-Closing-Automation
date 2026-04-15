from datetime import datetime
from typing import List, Any
from aiosmtplib import SMTP
from jinja2 import Template
from config import settings

REJECTION_TEMPLATE = Template("""
<html>
<body>
    <h2>File Rejection Alert</h2>
    <p>File for <strong>{{ employee_name }}</strong> ({{ employee_id }}) was rejected by <strong>{{ rejected_by }}</strong>.</p>
    <p><strong>Reason:</strong> {{ reason }}</p>
    <p>The file has been sent back to <strong>{{ target_department }}</strong>.</p>
</body>
</html>
""")

DAILY_TEMPLATE = Template("""
<html>
<body>
    <h2>Daily Clearance Summary - {{ date }}</h2>
    <p><strong>Pending files in your queue:</strong> {{ pending_count }}</p>
    <p><strong>Average processing time:</strong> {{ avg_time }} hours</p>
    {% if breached %}
    <h3 style="color:red;">Escalation List (SLA Breached)</h3>
    <ul>
        {% for b in breached %}
        <li>{{ b.employee_name }} - {{ b.current_department }} (Phase {{ b.current_phase }})</li>
        {% endfor %}
    </ul>
    {% else %}
    <p>No breached files.</p>
    {% endif %}
</body>
</html>
""")


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    """Helper to get attribute from SQLAlchemy model or dict."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


async def send_email(to_addresses: List[str], subject: str, html_body: str):
    try:
        smtp = SMTP(hostname=settings.SMTP_HOST, port=settings.SMTP_PORT)
        await smtp.connect()
        if settings.SMTP_USER:
            await smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        for addr in to_addresses:
            await smtp.sendmail(
                settings.SMTP_FROM,
                addr,
                f"Subject: {subject}\nContent-Type: text/html\n\n{html_body}"
            )
        await smtp.quit()
    except Exception as e:
        print(f"Email send failed: {e}")


async def send_rejection_alert(file: Any, reason: str, rejected_by: str):
    html = REJECTION_TEMPLATE.render(
        employee_name=_get_attr(file, "employee_name"),
        employee_id=_get_attr(file, "employee_id"),
        rejected_by=rejected_by,
        reason=reason,
        target_department=_get_attr(file, "current_department")
    )
    await send_email(["admin@ecp.com"], f"Rejection Alert: {_get_attr(file, 'employee_name')}", html)


async def send_daily_summary_sqlite(db):
    """SQLite version of daily summary."""
    from crud import get_all_files
    from models import StepStatus
    from collections import defaultdict

    files = await get_all_files(db)
    dept_files = defaultdict(list)
    for f in files:
        dept_files[f.current_department].append(f)

    for dept, f_list in dept_files.items():
        pending = [f for f in f_list if f.status != "COMPLETED"]
        breached = [f for f in pending if any(s.status == StepStatus.BREACHED for s in f.steps)]
        avg = 0
        if pending:
            total = sum(f.total_cycle_time for f in pending)
            avg = round(total / len(pending) / 60, 1)

        html = DAILY_TEMPLATE.render(
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            pending_count=len(pending),
            avg_time=avg,
            breached=breached
        )
        await send_email([f"{dept.lower().replace(', ', '_').replace(' ', '_')}@ecp.com"], "Daily Clearance Summary", html)


async def send_daily_summary_gsheets(crud):
    """Google Sheets version of daily summary."""
    from models import StepStatus
    from collections import defaultdict

    files = crud.get_all_files()
    dept_files = defaultdict(list)
    for f in files:
        dept_files[f["current_department"]].append(f)

    for dept, f_list in dept_files.items():
        pending = [f for f in f_list if f["status"] != "COMPLETED"]
        breached = []
        for f in pending:
            steps = crud.get_steps_for_file(f["id"])
            if any(s["sla_status"] == "BREACHED" or s["status"] == StepStatus.BREACHED.value for s in steps):
                breached.append(f)
        avg = 0
        if pending:
            total = sum(f["total_cycle_time"] for f in pending)
            avg = round(total / len(pending) / 60, 1)

        html = DAILY_TEMPLATE.render(
            date=datetime.utcnow().strftime("%Y-%m-%d"),
            pending_count=len(pending),
            avg_time=avg,
            breached=breached
        )
        await send_email([f"{dept.lower().replace(', ', '_').replace(' ', '_')}@ecp.com"], "Daily Clearance Summary", html)


async def send_daily_summary(db_or_crud):
    """Dispatch to SQLite or Google Sheets implementation."""
    try:
        from sqlalchemy.ext.asyncio import AsyncSession
        if isinstance(db_or_crud, AsyncSession):
            await send_daily_summary_sqlite(db_or_crud)
            return
    except ImportError:
        pass
    await send_daily_summary_gsheets(db_or_crud)
