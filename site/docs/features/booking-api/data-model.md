# Модель даних (`models.py`)

- `Tenant` (id-slug, `timezone`, `policy` JSONB), `Service` (`duration_min`, `price`), `Staff` (+ `StaffService`, `StaffSchedule`
  по днях тижня 0=Пн), `Client` (нормалізований `phone`, унікальний в межах тенанта).
- `Booking`: `start`/`end`, `status` (`scheduled|completed|cancelled|no_show`), `prepayment_amount/status`
  (`held|refunded|forfeited|none`), `no_show_fee_amount/status` (`charged|waived|none`), `notes`.
- `BookingEvent` (`ts`, `event`, `by`, `note`) -> `history`. Події дій: `rescheduled` (нотатка «старий -> новий старт. причина»),
  `cancelled`, `refunded`, `no_show_waived`, `goodwill`.
- `GoodwillException` (`client_id`, `booking_id`, `date`, `reason`), `OutgoingMessage`, `Ticket`, `Conversation`, `ChatMessage`.
- Усі id — рядки; нові `prefix-<6 hex>`. Схема створюється `Base.metadata.create_all`, без міграцій.
