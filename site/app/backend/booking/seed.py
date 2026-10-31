"""Deterministic demo seed. Everything is computed relative to the `now` argument."""
import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from booking.db import Base
from booking.models import (
    Booking, BookingEvent, Client, GoodwillException, Service, Staff,
    StaffSchedule, Tenant,
)
from booking.phone import normalize_phone

KYIV = ZoneInfo("Europe/Kyiv")

LUMEN_POLICY = {
    "cancellation_window_hours": 24, "late_change_forfeits_prepayment": True,
    "no_show_fee": 300, "prepayment_required": True,
    "agent_permissions": {
        "reschedule": "auto", "cancel": "auto", "refund": "auto_under_limit",
        "refund_auto_limit": 500, "goodwill_exception": "auto",
        "goodwill_per_client_per_180d": 1, "goodwill_requires_zero_no_shows": True,
        "waive_no_show_fee": "approval",
    },
}
DENTA_POLICY = {
    "cancellation_window_hours": 48, "late_change_forfeits_prepayment": True,
    "no_show_fee": 500, "prepayment_required": True,
    "agent_permissions": {
        "reschedule": "auto", "cancel": "approval", "refund": "approval",
        "refund_auto_limit": 0, "goodwill_exception": "approval",
        "goodwill_per_client_per_180d": 1, "goodwill_requires_zero_no_shows": True,
        "waive_no_show_fee": "forbidden",
    },
}

# tenant -> spec
TENANTS = {
    "lumen": dict(
        name="Lumen Beauty", kind="salon", policy=LUMEN_POLICY,
        description="Салон краси в центрі Києва: стрижки, фарбування, манікюр та догляд за бровами.",
        address="Київ, вул. Хрещатик, 22, 2 поверх", phone="+380442345678",
        instagram="lumen.beauty.kyiv", hours=(time(10), time(19)),
        services=[  # id, name, duration, price
            ("lumen-styling", "Стрижка + укладка", 60, 700),
            ("lumen-haircut", "Стрижка", 45, 500),
            ("lumen-coloring", "Фарбування", 120, 1800),
            ("lumen-manicure", "Манікюр", 60, 450),
            ("lumen-brows", "Корекція брів", 30, 300),
        ],
        staff=[  # id, name, service ids
            ("maria", "Марія", ["lumen-styling", "lumen-haircut", "lumen-coloring"]),
            ("sofia", "Софія", ["lumen-styling", "lumen-haircut", "lumen-manicure", "lumen-brows"]),
            ("katya", "Катерина", ["lumen-manicure", "lumen-brows", "lumen-coloring"]),
        ],
    ),
    "dentaplus": dict(
        name="DentaPlus", kind="clinic", policy=DENTA_POLICY,
        description="Сучасна стоматологічна клініка: консультації, лікування, гігієна та відбілювання.",
        address="Київ, вул. Саксаганського, 41", phone="+380445557788",
        instagram="dentaplus.kyiv", hours=(time(9), time(18)),
        services=[
            ("denta-consult", "Консультація", 30, 400),
            ("denta-cleaning", "Професійна чистка", 60, 1200),
            ("denta-filling", "Лікування карієсу", 60, 1500),
            ("denta-whitening", "Відбілювання", 90, 3500),
            ("denta-checkup", "Контрольний огляд", 30, 300),
        ],
        staff=[
            ("ostap", "Остап Бондар", ["denta-consult", "denta-filling", "denta-checkup"]),
            ("iryna", "Ірина Мельник", ["denta-consult", "denta-cleaning", "denta-whitening", "denta-checkup"]),
            ("taras", "Тарас Коваль", ["denta-filling", "denta-cleaning", "denta-checkup"]),
        ],
    ),
}

BG_NAMES = [
    "Оксана Шевченко", "Наталія Ткаченко", "Юлія Бондаренко", "Віктор Мороз",
    "Тетяна Кравчук", "Андрій Лисенко", "Світлана Гнатюк", "Дмитро Савченко",
    "Ірина Мазур", "Володимир Попович", "Лариса Руденко", "Богдан Юрченко",
    "Alina Koval", "Марина Олійник", "Євген Пономаренко", "Галина Романюк",
    "Артем Власенко", "Вікторія Яковенко", "Павло Захарченко", "Дарина Білик",
]

# (id, tenant, name, phone, notes)
DEMO_CLIENTS = [
    ("olena", "lumen", "Олена Коваленко", "380671234501", "Постійна клієнтка"),
    ("max", "lumen", "Максим Гончар", "380501234502", ""),
    ("ira", "lumen", "Ірина Петренко", "380931234503", ""),
    ("petro", "dentaplus", "Петро Сидоренко", "380671234504", ""),
    ("anna", "dentaplus", "Анна Кузьменко", "380991234505", ""),
]


def _dt(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=KYIV)


class _Seeder:
    def __init__(self, session: Session, now: datetime):
        self.s = session
        self.now = now.astimezone(KYIV)
        self.today = self.now.date()
        self.rng = random.Random(42)
        self.busy: dict[tuple[str, str], list[tuple[datetime, datetime]]] = {}
        self.counter: dict[str, int] = {}
        self.staff_of: dict[str, list[tuple[str, str, list[str]]]] = {}
        self.svc: dict[str, Service] = {}
        self.hours: dict[str, tuple[time, time]] = {}
        self.demo_days: set[tuple[str, date]] = set()

    # --- helpers -----------------------------------------------------------
    def free(self, keys, start, end) -> bool:
        return all(
            end <= bs or start >= be
            for k in keys for bs, be in self.busy.get(k, [])
        )

    def reserve(self, keys, start, end):
        for k in keys:
            self.busy.setdefault(k, []).append((start, end))

    def event(self, b: Booking, n: int, ts: datetime, event: str, by: str, note: str = ""):
        self.s.add(BookingEvent(id=f"ev-{b.id}-{n}", booking_id=b.id, ts=ts,
                                event=event, by=by, note=note))

    def add_booking(self, bid, tenant, client, staff, service, start, status="scheduled",
                    prepay=(0, "none"), fee=(0, "none"), notes="") -> Booking:
        sv = self.svc[service]
        end = start + timedelta(minutes=sv.duration_min)
        self.reserve([("s", staff), ("c", client)], start, end)
        b = Booking(id=bid, tenant_id=tenant, client_id=client, staff_id=staff,
                    service_id=service, start=start, end=end, status=status,
                    prepayment_amount=prepay[0], prepayment_status=prepay[1],
                    no_show_fee_amount=fee[0], no_show_fee_status=fee[1], notes=notes)
        self.s.add(b)
        self.s.flush()
        created = start - timedelta(days=3)
        self.event(b, 1, created, "created", "human:admin")
        if prepay[1] == "held":
            self.event(b, 2, created, "prepayment_held", "human:admin", f"{prepay[0]} грн")
        if status == "completed":
            self.event(b, 3, end, "completed", "human:admin")
        elif status == "no_show":
            self.event(b, 3, end, "no_show", "human:admin")
            if fee[1] == "charged":
                self.event(b, 4, end, "no_show_fee_charged", "human:admin", f"{fee[0]} грн")
        elif status == "cancelled":
            self.event(b, 3, created + timedelta(days=1), "cancelled", "human:admin")
        return b

    def next_id(self, tenant: str) -> str:
        self.counter[tenant] += 1
        return f"b-{tenant}-{self.counter[tenant]}"

    def staff_for(self, tenant, service):
        return [sid for sid, _, svs in self.staff_of[tenant] if service in svs]

    def grid(self, tenant, d: date, duration: int):
        lo, hi = self.hours[tenant]
        t = _dt(d, lo)
        last = _dt(d, hi) - timedelta(minutes=duration)
        out = []
        while t <= last:
            out.append(t)
            t += timedelta(minutes=30)
        return out

    def demo_past(self, tenant, client, service, n, status="completed", fixed_day: date | None = None,
                  fee=(0, "none"), notes="") -> Booking | None:
        """Add `n` past bookings 31..180 days ago (or one on fixed_day) in free slots."""
        last = None
        for _ in range(n):
            for _attempt in range(5000):
                d = fixed_day or self.today - timedelta(days=self.rng.randint(31, 180))
                sv = self.svc[service]
                start = self.rng.choice(self.grid(tenant, d, sv.duration_min))
                staff = self.rng.choice(self.staff_for(tenant, service))
                end = start + timedelta(minutes=sv.duration_min)
                if self.free([("s", staff), ("c", client)], start, end):
                    break
            else:
                raise RuntimeError(f"seed: no free slot for {client}")
            last = self.add_booking(self.next_id(tenant), tenant, client, staff, service,
                                    start, status, fee=fee, notes=notes)
        return last

    # --- build -------------------------------------------------------------
    def build(self):
        s = self.s
        for tid, spec in TENANTS.items():
            s.add(Tenant(id=tid, name=spec["name"], kind=spec["kind"], timezone="Europe/Kyiv",
                         description=spec["description"], address=spec["address"],
                         phone=spec["phone"], instagram=spec["instagram"], policy=spec["policy"]))
            s.flush()
            self.counter[tid] = 0
            self.hours[tid] = spec["hours"]
            self.staff_of[tid] = spec["staff"]
            for sid, name, dur, price in spec["services"]:
                sv = Service(id=sid, tenant_id=tid, name=name, duration_min=dur, price=price)
                s.add(sv)
                self.svc[sid] = sv
            s.flush()
            for stid, name, svs in spec["staff"]:
                s.add(Staff(id=stid, tenant_id=tid, name=name,
                            services=[self.svc[x] for x in svs]))
                s.flush()
                for wd in range(7):  # every day
                    s.add(StaffSchedule(staff_id=stid, weekday=wd,
                                        start_time=spec["hours"][0], end_time=spec["hours"][1]))
            s.flush()

        for cid, tid, name, phone, notes in DEMO_CLIENTS:
            s.add(Client(id=cid, tenant_id=tid, name=name, phone=normalize_phone(phone), notes=notes))
        s.flush()

        self.demo_core()
        self.background()
        s.commit()

    def demo_core(self):
        tomorrow = self.today + timedelta(days=1)
        yesterday = self.today - timedelta(days=1)
        in3 = self.today + timedelta(days=3)
        # Demo future/recent bookings first so that nothing collides with them.
        self.add_booking("b-olena-1", "lumen", "olena", "maria", "lumen-styling",
                         _dt(tomorrow, time(10)), prepay=(500, "held"))
        # Max is with Sofia (not Maria), so Maria's 11:00 tomorrow stays free.
        self.add_booking("b-max-1", "lumen", "max", "sofia", "lumen-haircut",
                         _dt(tomorrow, time(11)), prepay=(400, "held"))
        self.add_booking("b-ira-1", "lumen", "ira", "maria", "lumen-styling",
                         _dt(in3, time(15)), prepay=(500, "held"))
        self.add_booking("b-petro-1", "dentaplus", "petro", "ostap", "denta-consult",
                         _dt(tomorrow, time(9)), prepay=(800, "held"))
        self.add_booking("b-anna-1", "dentaplus", "anna", "ostap", "denta-consult",
                         _dt(yesterday, time(10)), status="no_show", fee=(500, "charged"))
        for staff, d in [("maria", tomorrow), ("sofia", tomorrow), ("maria", in3),
                         ("ostap", tomorrow), ("ostap", yesterday)]:
            self.demo_days.add((staff, d))

        # Own past history of the demo clients (counters derive from these only).
        self.demo_past("lumen", "olena", "lumen-styling", 12)
        self.demo_past("lumen", "max", "lumen-haircut", 2)
        self.demo_past("lumen", "max", "lumen-haircut", 2, status="no_show", fee=(300, "charged"))
        self.demo_past("lumen", "ira", "lumen-haircut", 4)
        gd = self.today - timedelta(days=30)
        gb = self.demo_past("lumen", "ira", "lumen-haircut", 1, fixed_day=gd,
                            notes="Пізнє скасування прощено як виняток")
        self.s.add(GoodwillException(id="gw-ira-1", client_id="ira", booking_id=gb.id,
                                     date=gd, reason="Разовий виняток щодо передоплати"))
        self.demo_past("dentaplus", "petro", "denta-checkup", 3)
        self.s.flush()

    def background(self):
        for tid, spec in TENANTS.items():
            clients = []
            for i in range(1, 21):
                cid = f"c-{tid}-{i}"
                phone = normalize_phone(f"+38 0{self.rng.choice(['67', '50', '93', '97', '63'])} "
                                        f"{self.rng.randint(1000000, 9999999)}")
                self.s.add(Client(id=cid, tenant_id=tid, name=BG_NAMES[i - 1], phone=phone, notes=""))
                clients.append(cid)
            self.s.flush()
            # past 29 days
            for stid, _, svs in spec["staff"]:
                for off in range(1, 30):
                    d = self.today - timedelta(days=off)
                    for _ in range(self.rng.randint(1, 3)):
                        self._try_place(tid, stid, svs, clients, d, past=True)
                # future 7 days: keep occupancy low
                avail = 7 * (spec["hours"][1].hour - spec["hours"][0].hour) * 60
                used = 0
                for _ in range(self.rng.randint(5, 8)):
                    d = self.today + timedelta(days=self.rng.randint(0, 6))
                    if (stid, d) in self.demo_days:
                        continue
                    used += self._try_place(tid, stid, svs, clients, d, past=False, cap=(avail * 0.35 - used))

    def _try_place(self, tid, stid, svs, clients, d, past, cap=10**9) -> int:
        sv = self.svc[self.rng.choice(svs)]
        start = self.rng.choice(self.grid(tid, d, sv.duration_min))
        end = start + timedelta(minutes=sv.duration_min)
        cid = self.rng.choice(clients)
        if sv.duration_min > cap or not self.free([("s", stid), ("c", cid)], start, end):
            return 0
        if past:
            status = self.rng.choices(["completed", "cancelled", "no_show"], [80, 12, 8])[0]
            fee = (TENANTS[tid]["policy"]["no_show_fee"], "charged") if status == "no_show" else (0, "none")
            self.add_booking(self.next_id(tid), tid, cid, stid, sv.id, start, status, fee=fee)
            return 0
        if start <= self.now:
            return 0
        self.add_booking(self.next_id(tid), tid, cid, stid, sv.id, start,
                         prepay=(sv.price // 4, "held"))
        return sv.duration_min


def seed(session: Session, now: datetime) -> None:
    _Seeder(session, now).build()


def reset(session: Session, now: datetime) -> None:
    session.rollback()
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()
    seed(session, now)
