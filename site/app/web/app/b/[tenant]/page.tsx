import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { api, ApiError } from "@/lib/api-core";
import { TENANT_KIND_LABEL, type Service, type Staff, type Tenant } from "@/lib/types";
import { policyToText } from "@/lib/policy-text";
import { formatDuration, formatPrice } from "@/lib/format";
import { Badge } from "@/components/ui/Badge";
import { LinkButton } from "@/components/ui/Button";

export const dynamic = "force-dynamic";

async function load(id: string) {
  try {
    const opts = { cache: "no-store" } as const;
    const [tenant, services, staff] = await Promise.all([
      api.get<Tenant>(`/api/tenants/${id}`, opts),
      api.get<Service[]>(`/api/tenants/${id}/services`, opts),
      api.get<Staff[]>(`/api/tenants/${id}/staff`, opts),
    ]);
    return { tenant, services, staff };
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata(props: PageProps<"/b/[tenant]">): Promise<Metadata> {
  const { tenant } = await props.params;
  try {
    const t = await api.get<Tenant>(`/api/tenants/${tenant}`, { cache: "no-store" });
    return { title: `${t.name} — онлайн-запис`, description: t.description };
  } catch {
    return {};
  }
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export default async function BusinessPage(props: PageProps<"/b/[tenant]">) {
  const { tenant: id } = await props.params;
  const { tenant, services, staff } = await load(id);
  const rules = policyToText(tenant.policy);
  const serviceById = new Map(services.map((s) => [s.id, s]));
  const phoneHref = `tel:${tenant.phone.replace(/[^\d+]/g, "")}`;

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <header className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="h-24 bg-gradient-to-r from-accent-600 to-accent-500 sm:h-32" />
        <div className="p-5 sm:p-6">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-semibold text-slate-900 sm:text-3xl">{tenant.name}</h1>
            <Badge color="accent">{TENANT_KIND_LABEL[tenant.kind]}</Badge>
          </div>
          <p className="mt-3 text-slate-600">{tenant.description}</p>
          <dl className="mt-4 space-y-1.5 text-sm text-slate-700">
            <div className="flex gap-2"><dt className="w-20 shrink-0 text-slate-500">Адреса</dt><dd>{tenant.address}</dd></div>
            <div className="flex gap-2">
              <dt className="w-20 shrink-0 text-slate-500">Телефон</dt>
              <dd><a href={phoneHref} className="text-accent-700 hover:underline">{tenant.phone}</a></dd>
            </div>
            {tenant.instagram && (
              <div className="flex gap-2">
                <dt className="w-20 shrink-0 text-slate-500">Instagram</dt>
                <dd>
                  <a href={`https://instagram.com/${tenant.instagram.replace(/^@/, "")}`} target="_blank" rel="noreferrer" className="text-accent-700 hover:underline">
                    @{tenant.instagram.replace(/^@/, "")}
                  </a>
                </dd>
              </div>
            )}
          </dl>
          <div className="mt-5 flex flex-wrap gap-2">
            <LinkButton href={`/b/${tenant.id}/book`} size="lg">Записатись</LinkButton>
            <LinkButton href={`/b/${tenant.id}/support`} variant="secondary" size="lg">Підтримка</LinkButton>
          </div>
        </div>
      </header>

      <Section title="Послуги">
        <ul className="divide-y divide-slate-100">
          {services.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0">
              <div>
                <p className="font-medium text-slate-900">{s.name}</p>
                <p className="text-sm text-slate-500">{formatDuration(s.duration_min)}</p>
              </div>
              <p className="shrink-0 font-semibold text-slate-900">{formatPrice(s.price)}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Майстри">
        <ul className="grid gap-3 sm:grid-cols-2">
          {staff.map((m) => (
            <li key={m.id} className="rounded-xl border border-slate-200 p-4">
              <div className="flex items-center gap-3">
                <span className="grid h-10 w-10 place-items-center rounded-full bg-accent-100 font-semibold text-accent-700">
                  {m.name.slice(0, 1)}
                </span>
                <p className="font-medium text-slate-900">{m.name}</p>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {m.service_ids.map((sid) => serviceById.get(sid)).filter((s): s is Service => !!s).map((s) => (
                  <Badge key={s.id}>{s.name}</Badge>
                ))}
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Правила">
        <ul className="space-y-2 text-sm text-slate-700">
          {rules.map((r) => (
            <li key={r} className="flex gap-2">
              <span aria-hidden className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent-500" />
              {r}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}
