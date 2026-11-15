"use client";

// Settings: rates and autonomy, saved searches, connected accounts, and the memory viewer (see and
// delete what GigBid has learned).
import { useState } from "react";
import useSWR from "swr";
import { Badge, Button, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import type { Schemas } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";

type SettingsIn = Schemas["SettingsIn"];

function Profile() {
  const { data, error, mutate } = useSWR("settings", endpoints.settings);
  const [form, setForm] = useState<SettingsIn | null>(null);
  const [saved, setSaved] = useState(false);
  if (error) return <ErrorState error={error} />;
  if (!data) return <Spinner />;
  const v = { ...(data as SettingsIn), ...(form ?? {}) };
  const num = (k: keyof SettingsIn, label: string, step = 1) => (
    <label className="block text-sm font-medium text-slate-700">
      {label}
      <input type="number" min={0} step={step} value={(v[k] as number | undefined) ?? ""}
             onChange={(e) => setForm({ ...(form ?? {}), [k]: e.target.value === "" ? null : Number(e.target.value) })}
             className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
    </label>
  );
  return (
    <Card title="Rates, budget and autonomy">
      <form className="grid gap-3 sm:grid-cols-2" onSubmit={async (e) => {
        e.preventDefault();
        await endpoints.saveSettings(form ?? {});
        setForm(null);
        setSaved(true);
        mutate();
      }}>
        {num("hourly_rate", "Your hourly rate (USD)")}
        {num("hourly_floor", "Lowest hourly rate you'll bid")}
        {num("fixed_floor", "Smallest fixed-price job (USD)")}
        {num("weekly_connects_budget", "Weekly Connects budget")}
        <label className="block text-sm font-medium text-slate-700 sm:col-span-2">
          Autonomy
          <select value={v.autonomy ?? "approve_everything"} onChange={(e) => setForm({ ...(form ?? {}), autonomy: e.target.value as SettingsIn["autonomy"] })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
            <option value="approve_everything">Ask me about every job</option>
            <option value="auto_skip_low_fit">Skip low-fit jobs automatically (never sends without me)</option>
          </select>
        </label>
        <div className="flex items-center gap-3 sm:col-span-2">
          <Button type="submit" disabled={!form}>Save</Button>
          {saved && !form && <span role="status" className="text-sm text-emerald-700">Saved</span>}
        </div>
      </form>
    </Card>
  );
}

function Searches() {
  const { data, error, mutate } = useSWR("searches", endpoints.searches);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<string>("");
  const [every, setEvery] = useState(60);
  if (error) return <ErrorState error={error} />;
  return (
    <Card title="Saved searches (Scout)">
      {!data ? <Spinner /> : (
        <ul className="mb-3 space-y-2">
          {data.length === 0 && <li className="text-sm text-slate-500">No saved searches. Scout runs only for these.</li>}
          {data.map((s) => (
            <li key={s.search_id} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 p-2 text-sm">
              <span>
                {s.query && <strong>“{s.query}” </strong>}{s.category && <Badge>{s.category.replace("_", " ")}</Badge>}
                <span className="ml-2 text-xs text-slate-500">every {s.every_minutes} min</span>
              </span>
              <Button variant="secondary" onClick={async () => { await endpoints.deleteSearch(s.search_id); mutate(); }} aria-label={`Delete search ${s.query ?? s.category}`}>Delete</Button>
            </li>
          ))}
        </ul>
      )}
      <form className="flex flex-wrap items-end gap-2" onSubmit={async (e) => {
        e.preventDefault();
        await endpoints.addSearch({ query: query || null, category: (category || null) as Schemas["SavedSearchIn"]["category"], every_minutes: every, skills: [] });
        setQuery("");
        mutate();
      }}>
        <label className="text-sm">Keywords<input value={query} onChange={(e) => setQuery(e.target.value)} className="mt-1 block rounded-lg border border-slate-300 px-2 py-1.5" /></label>
        <label className="text-sm">Category
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="mt-1 block rounded-lg border border-slate-300 px-2 py-1.5">
            <option value="">Any</option><option value="data_science">Data science</option><option value="development">Development</option>
            <option value="marketing">Marketing</option><option value="3d_design">3D design</option>
          </select>
        </label>
        <label className="text-sm">Every (min)<input type="number" min={15} max={1440} value={every} onChange={(e) => setEvery(Number(e.target.value))} className="mt-1 block w-24 rounded-lg border border-slate-300 px-2 py-1.5" /></label>
        <Button type="submit">Add</Button>
      </form>
    </Card>
  );
}

function Accounts() {
  const { data } = useSWR("health", endpoints.marketplaceHealth);
  return (
    <Card title="Connected accounts">
      <ul className="space-y-2 text-sm">
        <li className="flex items-center justify-between">GigSim marketplace
          <Badge tone={data?.marketplace === "ok" ? "good" : "warn"}>{data?.marketplace === "ok" ? `connected · ${data.connects_balance} Connects` : "unavailable"}</Badge></li>
        <li className="flex items-center justify-between">Upwork (official MCP, OAuth)<Badge>not connected</Badge></li>
        <li className="flex items-center justify-between">GitHub (repos for your portfolio)<Badge>not connected</Badge></li>
      </ul>
    </Card>
  );
}

function MemoryViewer() {
  const { data, error, mutate } = useSWR("memory", endpoints.memory);
  if (error) return <ErrorState error={error} />;
  if (!data) return <Spinner />;
  return (
    <Card title="What GigBid has learned">
      <p className="mb-3 text-xs text-slate-500">
        Style rules come only from your own edits, and only after the same change appears in 3 separate edits. Delete
        anything you don&apos;t want used.
      </p>
      <h3 className="mb-1 text-sm font-semibold">Style rules in use</h3>
      <ul className="mb-4 space-y-2" data-testid="style-rules">
        {data.style_rules.length === 0 && <li className="text-sm text-slate-500">None yet.</li>}
        {data.style_rules.map((r) => (
          <li key={r.key} className="flex items-center justify-between gap-2 rounded-lg border border-slate-200 p-2 text-sm">
            <span>{r.rule} <span className="text-xs text-slate-500">({r.evidence_edits} edits)</span></span>
            <Button variant="secondary" onClick={async () => { await endpoints.forget("style", r.key); mutate(); }}>Delete</Button>
          </li>
        ))}
      </ul>
      <h3 className="mb-1 text-sm font-semibold">Patterns being watched</h3>
      <ul className="mb-4 flex flex-wrap gap-2">
        {data.style_candidates.length === 0 && <li className="text-sm text-slate-500">None yet.</li>}
        {data.style_candidates.map((c) => (
          <li key={c.key}><Badge tone={(c.count ?? 0) >= 3 ? "good" : "neutral"}>{c.key.replace("never_say:", "avoid “") + (c.key.startsWith("never_say:") ? "”" : "")} · {c.count}/3</Badge></li>
        ))}
      </ul>
      <h3 className="mb-1 text-sm font-semibold">Outcomes by category</h3>
      {Object.keys(data.outcomes).length === 0 ? <p className="text-sm text-slate-500">None yet.</p> : (
        <ul className="text-sm">{Object.entries(data.outcomes).map(([k, v]) => <li key={k}>{k}: {v.submitted} sent, {v.replied + v.interview + v.hired} replied, {v.hired} hired</li>)}</ul>
      )}
    </Card>
  );
}

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Profile />
        <Searches />
        <Accounts />
        <MemoryViewer />
      </div>
    </>
  );
}
