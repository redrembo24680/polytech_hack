from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from booking.models import Service, Staff, StaffService, Tenant
from booking.services.bookings import is_slot_free

STEP_MIN = 60


def find_free_slots(session: Session, tenant: Tenant, service: Service, start: datetime,
                    end: datetime, staff_id: str | None, now: datetime) -> list[dict]:
    tz = ZoneInfo(tenant.timezone)
    q = (select(Staff).join(StaffService, StaffService.staff_id == Staff.id)
         .where(Staff.tenant_id == tenant.id, StaffService.service_id == service.id))
    if staff_id is not None:
        q = q.where(Staff.id == staff_id)
    staff_list = list(session.scalars(q))
    dur = timedelta(minutes=service.duration_min)
    out: list[dict] = []
    day = start.astimezone(tz).date()
    last = end.astimezone(tz).date()
    while day <= last:
        for st in staff_list:
            for row in st.schedule:
                if row.weekday != day.weekday():
                    continue
                s = datetime.combine(day, row.start_time, tzinfo=tz)
                row_end = datetime.combine(day, row.end_time, tzinfo=tz)
                while s + dur <= row_end:
                    if (start <= s < end and s >= now
                            and is_slot_free(session, st, s, s + dur)):
                        out.append({"staff_id": st.id, "staff_name": st.name,
                                    "start": s, "end": s + dur})
                    s += timedelta(minutes=STEP_MIN)
        day += timedelta(days=1)
    out.sort(key=lambda x: (x["start"], x["staff_name"]))
    return out
