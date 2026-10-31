# Модель даних

Тримати синхронно зі спекою апки (розділ 3) і `agent/models.py`. Усі id рядки, час ISO 8601 з таймзоною, гроші цілі гривні.

| Сутність | Ключові поля |
|---|---|
| Tenant | `id`, `name`, `kind` (salon/clinic), `timezone`, `policy` |
| Policy | `rules_text`, `cancellation_window_hours`, `late_change_forfeits_prepayment`, `no_show_fee`, `prepayment_required`, `agent_permissions` |
| AgentPermissions | `reschedule`, `cancel` (auto/approval); `refund` (auto_under_limit/approval/forbidden), `refund_auto_limit`; `goodwill_exception` (auto/approval/forbidden), `goodwill_per_client_per_180d`, `goodwill_requires_zero_no_shows`; `waive_no_show_fee` |
| Client | `id`, `tenant_id`, `name`, `phone`, `visits_count`, `no_show_count`, `goodwill_exceptions[]` (`date`, `booking_id`, `reason`), `notes` |
| Staff / Service | Staff: `id`, `name`, `service_ids`; Service: `id`, `name`, `duration_min`, `price` |
| Booking | `id`, `client_id`, `staff_id`, `service_id`, `start`, `end`, `status` (scheduled/completed/cancelled/no_show), `prepayment` (`amount`, `status` held/refunded/forfeited/none), `history[]` (`ts`, `event`, `by`, `note`) |
| Slot | `staff_id`, `staff_name`, `start`, `end` |
| Ticket | `id`, `client_id`, `summary`, `priority` (low/normal/high/urgent), `status` (open/closed), `ts` |
| OutgoingMessage | `id`, `client_id`, `channel` (chat/sms), `text`, `ts` |

## Сутності агента (`agent/events.py`)
- Event: `id` (наскрізний), `ts`, `session_id`, `tenant_id`, `type`, `payload`. Типи: `user_message`, `assistant_message`, `thinking`, `tool_call`, `tool_result`, `card`, `approval_created`, `approval_decided`, `error`.
- Approval: `id` (`ap-N`), `session_id`, `tenant_id`, `tool`, `args`, `reason`, `status` (pending/approved/rejected), `decided_by`, `note`, `created_at`, `decided_at`.
- Метрики (`metrics()`): `sessions`, `messages`, `tool_calls`, `auto_actions`, `approvals_pending/approved/rejected`, `escalations`, `money_saved_uah`.

## Tools
Read: `get_client_profile`, `get_booking`, `find_slots`. Write (policy gated): `reschedule_booking`, `cancel_booking`, `refund_prepayment`, `apply_goodwill_exception`, `waive_no_show_fee`, `escalate_to_human`. UI: `show_card`. Поле `by` в історії: `agent` або `human:<ім'я>`.

Стан тримається в пам'яті (`MemoryDataSource`, `EventLog`, `ApprovalStore`), скидається при рестарті; seed у `agent/seed.json` з відносними датами (`hours_ahead` — від поточної години, округленої вниз, або `day_offset` + `time` у бронюваннях; `days_ago` у винятках), перераховуються від `now` при старті.
