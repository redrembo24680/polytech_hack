# Структура фронтенда (`app/web`)

- `app/b/[tenant]/page.tsx` — серверний компонент, `force-dynamic`; 404 бекенда -> `notFound()`; `generateMetadata` з назвою бізнесу.
- `app/b/[tenant]/book/page.tsx` — серверна обгортка, що завантажує tenant/services/staff для клієнтського `BookingFlow`.
- `components/booking/BookingFlow.tsx` — `BookingFlow({tenant, services, staff})`, клієнтський: стан кроків, `useApi` для слотів, `api.post` для бронювання, `useToast` для помилок.
- `components/booking/BookingConfirmation.tsx` — `BookingConfirmation({tenant, booking, serviceName, staffName})`.
- `lib/policy-text.ts` — `policyToText(policy: Policy): string[]`; тест `lib/policy-text.test.ts` (vitest, `npm test`).
- `lib/format.ts` — `formatPrice`, `formatDuration`, `formatTime`, `formatDateTime`, `dateKey`, `dayBoundary`, `nextDays`, `dayLabel`; тест `lib/format.test.ts`.
- Використовує `components/ui` (Button/LinkButton, Input, Badge, Toast) і `lib/api` (клієнт) / `lib/api-core` (сервер).
