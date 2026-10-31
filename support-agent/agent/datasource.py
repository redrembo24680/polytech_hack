import json
import os
from collections.abc import Callable
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Protocol

import httpx
from zoneinfo import ZoneInfo

from agent.rules_text import RULES_TEXT_OVERRIDES
from agent.models import (
    Booking,
    Client,
    GoodwillException,
    HistoryEntry,
    OutgoingMessage,
    Prepayment,
    Service,
    Slot,
    Staff,
    Tenant,
    Ticket,
)

MAX_SLOTS = 12
SLOT_STEP = timedelta(minutes=60)


class DataError(Exception):
    """code is one of: not_found, invalid_state, slot_taken, validation."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class DataSource(Protocol):
    def list_tenants(self) -> list[Tenant]: ...
    def get_tenant(self, tenant_id: str) -> Tenant: ...
    def get_client(self, tenant_id: str, client_id: str) -> Client: ...
    def list_clients(self, tenant_id: str) -> list[Client]: ...
    def list_services(self, tenant_id: str) -> list[Service]: ...
    def list_staff(self, tenant_id: str) -> list[Staff]: ...
    def find_client_by_phone(self, tenant_id: str, phone: str) -> list[Client]: ...
    def list_client_bookings(self, tenant_id: str, client_id: str) -> list[Booking]: ...
    def get_booking(self, tenant_id: str, booking_id: str) -> Booking: ...
    def find_slots(
        self, tenant_id: str, service_id: str, from_dt: datetime, to_dt: datetime, staff_id: str | None = None
    ) -> list[Slot]: ...
    def reschedule(
        self, tenant_id: str, booking_id: str, start: datetime, staff_id: str | None,
        reason: str, by: str, forfeit_prepayment: bool,
    ) -> Booking: ...
    def cancel(self, tenant_id: str, booking_id: str, reason: str, by: str, forfeit_prepayment: bool) -> Booking: ...
    def refund(self, tenant_id: str, booking_id: str, amount: int, reason: str, by: str) -> Booking: ...
    def waive_no_show(self, tenant_id: str, booking_id: str, reason: str, by: str) -> Booking: ...
    def add_goodwill(self, tenant_id: str, client_id: str, booking_id: str, reason: str, by: str) -> Client: ...
    def send_message(self, tenant_id: str, client_id: str, channel: str, text: str) -> OutgoingMessage: ...
    def create_ticket(self, tenant_id: str, client_id: str, summary: str, priority: str) -> Ticket: ...


class MemoryDataSource(DataSource):
    def __init__(self, seed: dict, now: datetime, now_fn: Callable[[], datetime] | None = None):
        """`now` seeds the demo data; `now_fn` (default: frozen `now`) drives validation and timestamps."""
        self._now = now
        self._now_fn = now_fn or (lambda: now)
        self._tenants: dict[str, Tenant] = {}
        self._services: dict[str, dict[str, Service]] = {}
        self._staff: dict[str, dict[str, Staff]] = {}
        self._hours: dict[str, dict[str, tuple[time, time]]] = {}
        self._clients: dict[str, dict[str, Client]] = {}
        self._bookings: dict[str, dict[str, Booking]] = {}
        self._messages: list[OutgoingMessage] = []
        self._tickets: list[Ticket] = []
        for t in seed["tenants"]:
            self._load_tenant(t)

    @classmethod
    def from_file(cls, path: Path, now: datetime, now_fn: Callable[[], datetime] | None = None) -> "MemoryDataSource":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")), now, now_fn)

    # ---- seed loading ----

    def _load_tenant(self, t: dict) -> None:
        tid = t["id"]
        tz = ZoneInfo(t["timezone"])
        self._tenants[tid] = Tenant(
            id=tid, name=t["name"], kind=t["kind"], timezone=t["timezone"], policy=t["policy"]
        )
        self._services[tid] = {s["id"]: Service(tenant_id=tid, **s) for s in t["services"]}
        self._staff[tid] = {}
        self._hours[tid] = {}
        for s in t["staff"]:
            start_s, end_s = s["hours"]
            self._hours[tid][s["id"]] = (time.fromisoformat(start_s), time.fromisoformat(end_s))
            self._staff[tid][s["id"]] = Staff(
                id=s["id"], tenant_id=tid, name=s["name"], service_ids=s["service_ids"],
                hours=(start_s, end_s),
            )
        self._clients[tid] = {}
        for c in t["clients"]:
            exceptions = [
                GoodwillException(
                    date=self._now - timedelta(days=e["days_ago"]),
                    booking_id=e["booking_id"],
                    reason=e["reason"],
                )
                for e in c["goodwill_exceptions"]
            ]
            self._clients[tid][c["id"]] = Client(
                **{**c, "goodwill_exceptions": exceptions}, tenant_id=tid
            )
        self._bookings[tid] = {}
        for b in t["bookings"]:
            if "hours_ahead" in b:
                hour = self._now.astimezone(tz).replace(minute=0, second=0, microsecond=0)
                start = hour + timedelta(hours=b["hours_ahead"])
            else:
                hh, mm = map(int, b["time"].split(":"))
                day = (self._now + timedelta(days=b["day_offset"])).astimezone(tz)
                start = day.replace(hour=hh, minute=mm, second=0, microsecond=0)
            duration = self._services[tid][b["service_id"]].duration_min
            self._bookings[tid][b["id"]] = Booking(
                id=b["id"], tenant_id=tid, client_id=b["client_id"], staff_id=b["staff_id"],
                service_id=b["service_id"], start=start, end=start + timedelta(minutes=duration),
                status=b["status"], prepayment=Prepayment(**b["prepayment"]),
            )

    # ---- lookups ----

    def list_tenants(self) -> list[Tenant]:
        return list(self._tenants.values())

    def get_tenant(self, tenant_id: str) -> Tenant:
        try:
            return self._tenants[tenant_id]
        except KeyError:
            raise DataError("not_found", f"Тенанта {tenant_id} не знайдено") from None

    def get_client(self, tenant_id: str, client_id: str) -> Client:
        self.get_tenant(tenant_id)
        try:
            return self._clients[tenant_id][client_id]
        except KeyError:
            raise DataError("not_found", f"Клієнта {client_id} не знайдено") from None

    def list_services(self, tenant_id: str) -> list[Service]:
        self.get_tenant(tenant_id)
        return list(self._services[tenant_id].values())

    def list_staff(self, tenant_id: str) -> list[Staff]:
        self.get_tenant(tenant_id)
        return list(self._staff[tenant_id].values())

    def list_clients(self, tenant_id: str) -> list[Client]:
        self.get_tenant(tenant_id)
        return list(self._clients[tenant_id].values())

    def find_client_by_phone(self, tenant_id: str, phone: str) -> list[Client]:
        self.get_tenant(tenant_id)
        return [c for c in self._clients[tenant_id].values() if c.phone == phone]

    def list_client_bookings(self, tenant_id: str, client_id: str) -> list[Booking]:
        self.get_client(tenant_id, client_id)
        mine = [b for b in self._bookings[tenant_id].values() if b.client_id == client_id]
        return sorted(mine, key=lambda b: b.start, reverse=True)

    def get_booking(self, tenant_id: str, booking_id: str) -> Booking:
        self.get_tenant(tenant_id)
        try:
            return self._bookings[tenant_id][booking_id]
        except KeyError:
            raise DataError("not_found", f"Бронювання {booking_id} не знайдено") from None

    # ---- availability ----

    def _is_free(self, tenant_id: str, staff_id: str, start: datetime, end: datetime, ignore: str | None = None) -> bool:
        return not any(
            b.staff_id == staff_id and b.status == "scheduled" and b.id != ignore
            and b.start < end and start < b.end
            for b in self._bookings[tenant_id].values()
        )

    def find_slots(
        self, tenant_id: str, service_id: str, from_dt: datetime, to_dt: datetime, staff_id: str | None = None
    ) -> list[Slot]:
        tenant = self.get_tenant(tenant_id)
        service = self._services[tenant_id].get(service_id)
        if service is None:
            raise DataError("not_found", f"Послугу {service_id} не знайдено")
        tz = ZoneInfo(tenant.timezone)
        duration = timedelta(minutes=service.duration_min)
        staff_list = [
            s for s in self._staff[tenant_id].values()
            if service_id in s.service_ids and (staff_id is None or s.id == staff_id)
        ]
        slots: list[Slot] = []
        now = self._now_fn()
        day = from_dt.astimezone(tz).date()
        last_day = to_dt.astimezone(tz).date()
        while day <= last_day:
            for s in staff_list:
                open_t, close_t = self._hours[tenant_id][s.id]
                cur = datetime.combine(day, open_t, tzinfo=tz)
                close = datetime.combine(day, close_t, tzinfo=tz)
                while cur + duration <= close:
                    if cur >= now and self._is_free(tenant_id, s.id, cur, cur + duration):
                        slots.append(Slot(staff_id=s.id, staff_name=s.name, start=cur, end=cur + duration))
                    cur += SLOT_STEP
            day += timedelta(days=1)
        slots.sort(key=lambda s: (s.start, s.staff_id))
        return slots[:MAX_SLOTS]

    # ---- mutations ----

    def _validate_start(self, tenant_id: str, service_id: str, staff_id: str, start: datetime, end: datetime) -> None:
        if start < self._now_fn():
            raise DataError("validation", "Не можна перенести бронювання на час у минулому")
        if service_id not in self._staff[tenant_id][staff_id].service_ids:
            raise DataError("validation", "Цей майстер не надає обрану послугу")
        tz = ZoneInfo(self._tenants[tenant_id].timezone)
        local_start, local_end = start.astimezone(tz), end.astimezone(tz)
        open_t, close_t = self._hours[tenant_id][staff_id]
        if (
            local_start.date() != local_end.date()
            or local_start.time() < open_t
            or local_end.time() > close_t
        ):
            raise DataError("validation", "Цей час поза робочими годинами майстра")

    def _log(self, booking: Booking, event: str, by: str, note: str) -> None:
        booking.history.append(HistoryEntry(ts=self._now_fn(), event=event, by=by, note=note))

    def reschedule(
        self, tenant_id: str, booking_id: str, start: datetime, staff_id: str | None,
        reason: str, by: str, forfeit_prepayment: bool,
    ) -> Booking:
        b = self.get_booking(tenant_id, booking_id)
        if b.status != "scheduled":
            raise DataError("invalid_state", f"Бронювання {booking_id} має статус {b.status}, перенести неможливо")
        target_staff = staff_id or b.staff_id
        if target_staff not in self._staff[tenant_id]:
            raise DataError("not_found", f"Майстра {target_staff} не знайдено")
        end = start + (b.end - b.start)
        self._validate_start(tenant_id, b.service_id, target_staff, start, end)
        if not self._is_free(tenant_id, target_staff, start, end, ignore=b.id):
            raise DataError("slot_taken", "Цей слот уже зайнятий")
        b.start, b.end, b.staff_id = start, end, target_staff
        if forfeit_prepayment and b.prepayment.status == "held":
            b.prepayment.status = "forfeited"
        self._log(b, "rescheduled", by, reason)
        return b

    def cancel(self, tenant_id: str, booking_id: str, reason: str, by: str, forfeit_prepayment: bool) -> Booking:
        b = self.get_booking(tenant_id, booking_id)
        if b.status != "scheduled":
            raise DataError("invalid_state", f"Бронювання {booking_id} має статус {b.status}, скасувати неможливо")
        b.status = "cancelled"
        if forfeit_prepayment and b.prepayment.status == "held":
            b.prepayment.status = "forfeited"
        self._log(b, "cancelled", by, reason)
        return b

    def refund(self, tenant_id: str, booking_id: str, amount: int, reason: str, by: str) -> Booking:
        b = self.get_booking(tenant_id, booking_id)
        if b.prepayment.status != "held":
            raise DataError("invalid_state", f"Передоплата має статус {b.prepayment.status}, повернути неможливо")
        if amount <= 0 or amount > b.prepayment.amount:
            raise DataError("validation", f"Сума повернення має бути від 1 до {b.prepayment.amount} грн")
        b.prepayment.status = "refunded"
        self._log(b, "refunded", by, reason)
        return b

    def waive_no_show(self, tenant_id: str, booking_id: str, reason: str, by: str) -> Booking:
        b = self.get_booking(tenant_id, booking_id)
        if b.status != "no_show":
            raise DataError("invalid_state", f"Бронювання {booking_id} має статус {b.status}, а не no_show")
        self._log(b, "no_show_fee_waived", by, reason)
        return b

    def add_goodwill(self, tenant_id: str, client_id: str, booking_id: str, reason: str, by: str) -> Client:
        c = self.get_client(tenant_id, client_id)
        b = self.get_booking(tenant_id, booking_id)
        c.goodwill_exceptions.append(GoodwillException(date=self._now_fn(), booking_id=booking_id, reason=reason))
        self._log(b, "goodwill_applied", by, reason)
        return c

    def send_message(self, tenant_id: str, client_id: str, channel: str, text: str) -> OutgoingMessage:
        self.get_client(tenant_id, client_id)
        msg = OutgoingMessage(
            id=f"msg-{len(self._messages) + 1}", tenant_id=tenant_id, client_id=client_id,
            channel=channel, text=text, ts=self._now_fn(),
        )
        self._messages.append(msg)
        return msg

    def create_ticket(self, tenant_id: str, client_id: str, summary: str, priority: str) -> Ticket:
        self.get_client(tenant_id, client_id)
        ticket = Ticket(
            id=f"tkt-{len(self._tickets) + 1}", tenant_id=tenant_id, client_id=client_id,
            summary=summary, priority=priority, status="open", ts=self._now_fn(),
        )
        self._tickets.append(ticket)
        return ticket


KYIV = ZoneInfo("Europe/Kyiv")
UNAVAILABLE_TEXT = "Платформа бронювань недоступна."


def _goodwill_date(raw: str) -> datetime:
    if len(raw) == 10:  # YYYY-MM-DD
        return datetime.combine(datetime.fromisoformat(raw).date(), time.min, tzinfo=KYIV)
    return datetime.fromisoformat(raw)


class HttpDataSource(DataSource):
    """Клієнт REST API платформи бронювань (`/api/tenants/{tenant_id}/...`)."""

    def __init__(self, base_url: str, timeout: float = 15, transport: httpx.BaseTransport | None = None):
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)

    def _call(self, method: str, path: str, *, params: dict | None = None, json_body: dict | None = None):
        try:
            r = self._http.request(method, path, params=params, json=json_body)
        except httpx.HTTPError:
            raise DataError("api_unavailable", UNAVAILABLE_TEXT) from None
        try:
            data = r.json()
        except ValueError:
            data = None
        if r.is_success:
            return data
        if isinstance(data, dict) and data.get("error"):
            raise DataError(str(data["error"]), str(data.get("message") or data["error"]))
        if r.status_code == 422:
            raise DataError("validation", "Некоректний запит.")
        if r.status_code >= 500:
            raise DataError("api_unavailable", UNAVAILABLE_TEXT)
        raise DataError("api_error", f"Платформа відповіла HTTP {r.status_code}.")

    def _t(self, tenant_id: str, path: str = "") -> str:
        return f"/api/tenants/{tenant_id}{path}"

    @staticmethod
    def _client(data: dict) -> Client:
        data = {**data, "goodwill_exceptions": [
            {**g, "date": _goodwill_date(g["date"])} for g in data.get("goodwill_exceptions") or []]}
        return Client.model_validate(data)

    def list_tenants(self) -> list[Tenant]:
        return [self._tenant(t) for t in self._call("GET", "/api/tenants")]

    @staticmethod
    def _tenant(data: dict) -> Tenant:
        tenant = Tenant.model_validate(data)
        if not tenant.policy.rules_text:
            tenant.policy.rules_text = RULES_TEXT_OVERRIDES.get(tenant.id, "")
        return tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        return self._tenant(self._call("GET", self._t(tenant_id)))

    def get_client(self, tenant_id: str, client_id: str) -> Client:
        return self._client(self._call("GET", self._t(tenant_id, f"/clients/{client_id}")))

    def list_services(self, tenant_id: str) -> list[Service]:
        return [Service.model_validate(x) for x in self._call("GET", self._t(tenant_id, "/services"))]

    def list_staff(self, tenant_id: str) -> list[Staff]:
        return [Staff.model_validate(x) for x in self._call("GET", self._t(tenant_id, "/staff"))]

    def list_clients(self, tenant_id: str) -> list[Client]:
        return [self._client(c) for c in self._call("GET", self._t(tenant_id, "/clients"))]

    def find_client_by_phone(self, tenant_id: str, phone: str) -> list[Client]:
        data = self._call("GET", self._t(tenant_id, "/clients"), params={"phone": phone})
        return [self._client(c) for c in data]

    def list_client_bookings(self, tenant_id: str, client_id: str) -> list[Booking]:
        data = self._call("GET", self._t(tenant_id, f"/clients/{client_id}"))
        return [Booking.model_validate(b) for b in data.get("bookings") or []]

    def get_booking(self, tenant_id: str, booking_id: str) -> Booking:
        return Booking.model_validate(self._call("GET", self._t(tenant_id, f"/bookings/{booking_id}")))

    def find_slots(
        self, tenant_id: str, service_id: str, from_dt: datetime, to_dt: datetime, staff_id: str | None = None
    ) -> list[Slot]:
        params = {"service_id": service_id, "from": from_dt.isoformat(), "to": to_dt.isoformat()}
        if staff_id:
            params["staff_id"] = staff_id
        data = self._call("GET", self._t(tenant_id, "/slots"), params=params)
        return [Slot.model_validate(s) for s in data][:MAX_SLOTS]

    def _booking_action(self, tenant_id: str, booking_id: str, action: str, body: dict) -> Booking:
        return Booking.model_validate(
            self._call("POST", self._t(tenant_id, f"/bookings/{booking_id}/{action}"), json_body=body))

    def reschedule(
        self, tenant_id: str, booking_id: str, start: datetime, staff_id: str | None,
        reason: str, by: str, forfeit_prepayment: bool,
    ) -> Booking:
        body = {"start": start.isoformat(), "reason": reason, "by": by, "forfeit_prepayment": forfeit_prepayment}
        if staff_id:
            body["staff_id"] = staff_id
        return self._booking_action(tenant_id, booking_id, "reschedule", body)

    def cancel(self, tenant_id: str, booking_id: str, reason: str, by: str, forfeit_prepayment: bool) -> Booking:
        return self._booking_action(tenant_id, booking_id, "cancel",
                                    {"reason": reason, "by": by, "forfeit_prepayment": forfeit_prepayment})

    def refund(self, tenant_id: str, booking_id: str, amount: int, reason: str, by: str) -> Booking:
        return self._booking_action(tenant_id, booking_id, "refund", {"amount": amount, "reason": reason, "by": by})

    def waive_no_show(self, tenant_id: str, booking_id: str, reason: str, by: str) -> Booking:
        return self._booking_action(tenant_id, booking_id, "waive-no-show", {"reason": reason, "by": by})

    def add_goodwill(self, tenant_id: str, client_id: str, booking_id: str, reason: str, by: str) -> Client:
        return self._client(self._call("POST", self._t(tenant_id, f"/clients/{client_id}/goodwill"),
                                       json_body={"booking_id": booking_id, "reason": reason, "by": by}))

    def send_message(self, tenant_id: str, client_id: str, channel: str, text: str) -> OutgoingMessage:
        return OutgoingMessage.model_validate(
            self._call("POST", self._t(tenant_id, "/messages"),
                       json_body={"client_id": client_id, "channel": channel, "text": text}))

    def create_ticket(self, tenant_id: str, client_id: str, summary: str, priority: str) -> Ticket:
        return Ticket.model_validate(
            self._call("POST", self._t(tenant_id, "/tickets"),
                       json_body={"client_id": client_id, "summary": summary, "priority": priority}))


def make_datasource(now_fn: Callable[[], datetime]) -> DataSource:
    """APP_API_URL задано -> платформа тіммейта по HTTP, інакше демо-дані в пам'яті."""
    url = os.environ.get("APP_API_URL")
    if url:
        return HttpDataSource(url)
    return MemoryDataSource.from_file(Path(__file__).parent / "seed.json", now_fn(), now_fn=now_fn)
