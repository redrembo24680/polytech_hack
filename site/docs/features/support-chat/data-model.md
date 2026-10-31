# Модель даних

- `Conversation`: `id` (`conv-xxxxxx`), `tenant_id`, `client_id` (null, якщо телефон невідомий), `status` (`open|closed`),
  `created_at`, `visitor_name`, `visitor_phone` (нормалізований до цифр).
- `ChatMessage`: `id` (`cm-xxxxxx`), `conversation_id`, `role` (`client|agent|human`), `text`, `ts` (ISO з офсетом; у межах
  розмови строго зростає, тому `?after=<ts>` не губить повідомлень).
- Клієнтський стан: `localStorage["support:<tenant>"] = {"conversationId": "..."}`.
