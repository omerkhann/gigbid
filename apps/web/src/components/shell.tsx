"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import useSWR from "swr";
import { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { useLiveConnection, useRunEvents } from "@/lib/events";
import { Spinner, cx } from "./ui";

const NAV = [
  { href: "/inbox", label: "Inbox" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/messages", label: "Messages" },
  { href: "/runs", label: "Agent runs" },
  { href: "/analytics", label: "Analytics" },
  { href: "/settings", label: "Settings" },
];

function MarketplaceBanner() {
  const { data } = useSWR("health", endpoints.marketplaceHealth, { refreshInterval: 20_000 });
  if (!data || data.marketplace === "ok") return null;
  return (
    <div role="alert" data-testid="marketplace-banner" className="border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900">
      <strong>Marketplace unavailable.</strong> GigBid can&apos;t reach the marketplace right now. Analyses wait and
      resume automatically; nothing is lost and nothing is sent until it&apos;s back.
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const path = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const me = useSWR("me", endpoints.me, { shouldRetryOnError: false });
  const approvals = useSWR("approvals", endpoints.approvals, { refreshInterval: 30_000 });
  const live = useLiveConnection();
  useRunEvents((e) => {
    if (e.type !== "node") approvals.mutate();
  });

  useEffect(() => {
    if (me.error instanceof ApiError && me.error.status === 401) router.replace("/login");
  }, [me.error, router]);

  if (!me.data) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        {me.error && !(me.error instanceof ApiError && me.error.status === 401) ? (
          <p role="alert" className="text-sm text-rose-700">Can&apos;t reach the GigBid API. Is it running?</p>
        ) : (
          <Spinner label="Signing you in" />
        )}
      </div>
    );
  }

  const pending = approvals.data?.length ?? 0;
  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {NAV.map((n) => (
        <Link
          key={n.href}
          href={n.href}
          onClick={() => setMenuOpen(false)}
          aria-current={path.startsWith(n.href) ? "page" : undefined}
          className={cx(
            "flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium",
            path.startsWith(n.href) ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100",
          )}
        >
          {n.label}
          {n.href === "/inbox" && pending > 0 && (
            <span className="rounded-full bg-violet-600 px-2 text-xs text-white" aria-label={`${pending} awaiting approval`}>
              {pending}
            </span>
          )}
        </Link>
      ))}
    </nav>
  );

  async function logout() {
    await endpoints.logout().catch(() => undefined);
    router.replace("/login");
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <MarketplaceBanner />
      <div className="flex flex-1">
        <aside className="hidden w-60 shrink-0 flex-col gap-6 border-r border-slate-200 bg-white p-4 md:flex">
          <Link href="/inbox" className="text-lg font-bold text-slate-900">
            GigBid
          </Link>
          {nav}
          <div className="mt-auto space-y-2 text-xs text-slate-500">
            <p>
              <span className={cx("mr-1 inline-block h-2 w-2 rounded-full", live ? "bg-emerald-500" : "bg-slate-300")} />
              {live ? "Live updates on" : "Live updates reconnecting"}
            </p>
            <p className="truncate">{me.data.name} · {me.data.persona?.replace("_", " ")}</p>
            <button onClick={logout} className="font-medium text-slate-700 hover:underline">
              Sign out
            </button>
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
            <Link href="/inbox" className="font-bold">GigBid</Link>
            <button
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              onClick={() => setMenuOpen((o) => !o)}
              className="rounded-lg px-3 py-1 text-sm ring-1 ring-slate-300"
            >
              Menu{pending > 0 ? ` (${pending})` : ""}
            </button>
          </header>
          {menuOpen && (
            <div id="mobile-nav" className="border-b border-slate-200 bg-white p-3 md:hidden">
              {nav}
              <button onClick={logout} className="mt-2 px-3 text-sm text-slate-600">Sign out</button>
            </div>
          )}
          <main className="mx-auto w-full max-w-6xl flex-1 p-4 md:p-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
