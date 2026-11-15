"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import useSWR from "swr";
import { ApiError } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { useLiveConnection, useRunEvents } from "@/lib/events";
import { Spinner, cx } from "./ui";

// Outline icons (24x24 paths), decorative only: each link keeps its text label as the accessible name.
const ICONS: Record<string, string> = {
  "/inbox": "M3 13h4l2 3h6l2-3h4M5 5h14l2 8v6H3v-6l2-8z",
  "/pipeline": "M4 5h4v14H4zM10 5h4v9h-4zM16 5h4v5h-4z",
  "/messages": "M4 5h16v11H8l-4 4V5z",
  "/runs": "M13 3L4 14h7l-1 7 9-11h-7l1-7z",
  "/analytics": "M4 20V10M10 20V4M16 20v-7M22 20H2",
  "/settings": "M12 9a3 3 0 100 6 3 3 0 000-6zM19 12l2-1-2-4-2 1-2-2V3h-4v3L9 7 7 6 5 10l2 1v2l-2 1 2 4 2-1 2 2v3h4v-3l2-2 2 1 2-4-2-1z",
};

const NAV = [
  { href: "/inbox", label: "Inbox" },
  { href: "/pipeline", label: "Pipeline" },
  { href: "/messages", label: "Messages" },
  { href: "/runs", label: "Agent runs" },
  { href: "/analytics", label: "Analytics" },
  { href: "/settings", label: "Settings" },
];

function Icon({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"
         className="h-4 w-4 shrink-0" aria-hidden>
      <path d={d} />
    </svg>
  );
}

function Brand() {
  return (
    <Link href="/inbox" className="flex items-center gap-2.5" aria-label="GigBid">
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white shadow-sm shadow-emerald-500/30" aria-hidden>
        G
      </span>
      <span className="leading-tight" aria-hidden>
        <span className="block text-base font-bold tracking-tight text-slate-900">GigBid</span>
        <span className="block text-[11px] font-medium text-slate-500">Freelance copilot</span>
      </span>
    </Link>
  );
}

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
            "group flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium transition",
            path.startsWith(n.href)
              ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-100"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
          )}
        >
          <span className="flex items-center gap-2.5">
            <span className={path.startsWith(n.href) ? "text-emerald-600" : "text-slate-400 group-hover:text-slate-600"}>
              <Icon d={ICONS[n.href]} />
            </span>
            {n.label}
          </span>
          {n.href === "/inbox" && pending > 0 && (
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-[11px] font-semibold text-white" aria-label={`${pending} awaiting approval`}>
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
    <div className="flex min-h-screen flex-col">
      <MarketplaceBanner />
      <div className="flex flex-1">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col gap-7 border-r border-slate-200/80 bg-white/80 p-5 backdrop-blur md:flex">
          <Brand />
          <div>
            <p className="mb-2 px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Workspace</p>
            {nav}
          </div>
          <div className="mt-auto space-y-3">
            <p className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
              <span className={cx("relative inline-flex h-2 w-2 rounded-full", live ? "bg-emerald-500" : "bg-slate-300")}>
                {live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />}
              </span>
              {live ? "Live updates on" : "Live updates reconnecting"}
            </p>
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 p-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-sm font-semibold text-emerald-700" aria-hidden>
                {(me.data.name || "?").slice(0, 1).toUpperCase()}
              </span>
              <div className="min-w-0 text-xs">
                <p className="truncate font-semibold text-slate-900">{me.data.name}</p>
                <p className="truncate capitalize text-slate-500">{me.data.persona?.replace("_", " ")}</p>
                <button onClick={logout} className="mt-0.5 font-medium text-emerald-600 hover:underline">
                  Sign out
                </button>
              </div>
            </div>
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
            <Brand />
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
