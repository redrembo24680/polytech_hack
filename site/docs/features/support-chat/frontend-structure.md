# Структура фронтенду (`app/web`)

- `app/b/[tenant]/support/page.tsx` — серверна сторінка, віддає `<SupportChat tenant>`.
- `components/chat/SupportChat.tsx` — стан чату: старт/відновлення, оптимістичне надсилання, опитування `?after=` (2 с), дедуп за `id`, автоскрол, Enter/Shift+Enter.
- `components/chat/StartForm.tsx` — форма «Ім'я/Телефон» (обидва обов'язкові).
- `components/chat/MessageBubble.tsx` — `MessageBubble` (client праворуч, agent/human ліворуч з підписом) і `TypingIndicator`.
- `components/layout/SiteChrome.tsx` — шапка сайту й обгортка `<main>`; при `?embed=1` шапка не рендериться, `<main>` на всю висоту.
  Клієнтський компонент із `useSearchParams` у кореневому layout (у `Suspense`): працює для всіх сторінок і дає чистий SSR-HTML без шапки.
