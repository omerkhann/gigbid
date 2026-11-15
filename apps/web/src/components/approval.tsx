"use client";

// Approve / edit / reject a pending proposal or message. The decision is queued; the worker resumes
// the checkpointed graph, and this panel waits for the live "finished" event (or polls) before
// telling the user it's done.
import { useState } from "react";
import type { ApprovalIn } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import { useRunEvents } from "@/lib/events";
import { StatusBadge } from "./badges";
import { Button } from "./ui";

export function ApprovalPanel({
  threadId,
  kind,
  edited,
  onDone,
  sendLabel,
}: {
  threadId: string;
  kind: "proposal" | "message";
  edited: { cover_letter?: string; screening_answers?: string[]; bid_amount?: number } | null;
  onDone: () => void;
  sendLabel: string;
}) {
  const [busy, setBusy] = useState<null | "approve" | "edit" | "reject">(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  useRunEvents((e) => {
    if (busy && e.type !== "node") {
      setResult(e.status ?? null);
      setBusy(null);
      onDone();
    }
  }, threadId);

  async function decide(body: ApprovalIn) {
    setBusy(body.action);
    setError(null);
    try {
      await endpoints.decide(threadId, body);
      // Fallback if live events aren't connected: check the run after a moment.
      setTimeout(async () => {
        const r = await endpoints.run(threadId).catch(() => null);
        if (r && r.status !== "running") {
          setResult(r.status ?? null);
          setBusy(null);
          onDone();
        }
      }, 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
      setBusy(null);
    }
  }

  if (result) {
    return (
      <div role="status" className="rounded-xl border border-slate-200 bg-white p-4 text-sm" data-testid="approval-result">
        Done: <StatusBadge status={result} />
        {result === "awaiting_approval" && <p className="mt-1 text-slate-600">Your edit was re-checked by Compliance. Review it again below.</p>}
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-600">
        {kind === "proposal"
          ? "Approving submits this proposal to the marketplace and spends the Connects shown."
          : "Approving sends this message to the client."}
      </p>
      {busy && <p role="status" className="text-sm text-sky-700">Queued. The agents are working on it…</p>}
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <Button variant="good" disabled={!!busy} onClick={() => decide({ action: "approve" })} data-testid="approve">
          {busy === "approve" ? "Sending…" : sendLabel}
        </Button>
        <Button
          variant="secondary"
          disabled={!!busy || !edited}
          title={edited ? "Send your edits through Compliance, then approve again" : "Edit the draft first"}
          onClick={() => edited && decide({ action: "edit", ...edited })}
          data-testid="save-edit"
        >
          {busy === "edit" ? "Re-checking…" : "Save edit"}
        </Button>
        <Button variant="danger" disabled={!!busy} onClick={() => setRejecting((r) => !r)} aria-expanded={rejecting}>
          Reject
        </Button>
      </div>
      {rejecting && (
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            decide({ action: "reject", reason });
          }}
        >
          <label className="sr-only" htmlFor="reject-reason">Reason</label>
          <input
            id="reject-reason"
            required
            minLength={3}
            placeholder="Why? (helps GigBid learn)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <Button variant="danger" type="submit" disabled={!!busy} data-testid="confirm-reject">
            Confirm reject
          </Button>
        </form>
      )}
    </div>
  );
}
