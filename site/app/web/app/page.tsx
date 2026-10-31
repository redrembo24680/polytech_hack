import { api } from "@/lib/api-core";
import { TENANT_KIND_LABEL, type Tenant } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { LinkButton } from "@/components/ui/Button";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let tenants: Tenant[] = [];
  let failed = false;
  try {
    tenants = await api.get<Tenant[]>("/api/tenants", { cache: "no-store" });
  } catch {
    failed = true;
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-slate-900">Оберіть бізнес</h1>
      <p className="mt-1 text-slate-600">Онлайн-запис, підтримка клієнтів та адмінка в одному місці.</p>

      {failed && (
        <p role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Не вдалося завантажити список бізнесів. Спробуйте оновити сторінку.
        </p>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {tenants.map((t) => (
          <article key={t.id} className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-lg font-semibold text-slate-900">{t.name}</h2>
              <Badge color="accent">{TENANT_KIND_LABEL[t.kind]}</Badge>
            </div>
            <p className="mt-2 flex-1 text-sm text-slate-600">{t.address}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              <LinkButton href={`/b/${t.id}`}>Сторінка бізнесу</LinkButton>
              <LinkButton href={`/admin/${t.id}`} variant="secondary">
                Адмінка
              </LinkButton>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
