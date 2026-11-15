"use client";

// One conversation: messages, the suggested reply (with intent, scam flags and offered interview
// slots), and approve / edit / reject.
import { useParams } from "next/navigation";
import { useState } from "react";
import useSWR from "swr";
import { ApprovalPanel } from "@/components/approval";
import { when } from "@/components/badges";
import { Badge, Button, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import { useRunEvents } from "@/lib/events";
import type { MessageApproval } from "@/lib/types";

export default function ThreadPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, isLoading, mutate } = useSWR(["thread", id], () => endpoints.thread(id));
  const [body, setBody] = useState<string | null>(null);
  const [drafting, setDrafting] = useState(false);
  useRunEvents((e) => {
    if (e.type !== "node") {
      setDrafting(false);
      mutate();
    }
  }, data?.run_thread);

  if (isLoading) return <Spinner />;
  if (error) return <ErrorState error={error} retry={() => mutate()} />;
  if (!data) return null;
  const pending = data.pending_reply as MessageApproval | null;
  const scam = pending?.intent.flags.includes("scam_signal");

  async function draft() {
    setDrafting(true);
    await endpoints.draftReply(id);
  }

  return (
    <>
      <PageHeader title="Conversation" subtitle={`Proposal status: ${data.status}`}
                  actions={!pending && data.accepting_messages ? <Button onClick={draft} disabled={drafting}>{drafting ? "Drafting…" : "Draft a reply"}</Button> : null} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Messages" className="lg:col-span-2">
          <ol className="space-y-3">
            {data.messages.map((m, i) => (
              <li key={i} className={`max-w-[85%] rounded-xl p-3 text-sm ${m.sender === "client" ? "bg-slate-100" : "ml-auto bg-sky-50"}`}>
                <p className="mb-1 text-xs font-medium text-slate-500">{m.sender === "client" ? "Client" : "You"} · {when(m.at)}</p>
                <p className="whitespace-pre-wrap text-slate-800">{m.body}</p>
              </li>
            ))}
          </ol>
        </Card>
        <div className="space-y-4">
          {pending ? (
            <>
              <Card title="Suggested reply" actions={<Badge tone={scam ? "bad" : "info"}>{pending.intent.intent.replace("_", " ")}</Badge>}>
                {scam && (
                  <p role="alert" className="mb-2 rounded-lg bg-rose-50 p-2 text-xs text-rose-800">
                    This client asked for something outside the platform rules (off-platform contact, fees or unpaid work).
                    The reply keeps things on the platform.
                  </p>
                )}
                {pending.intent.flags.includes("prompt_injection") && (
                  <p className="mb-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">The message contained instructions aimed at AI tools; they were ignored.</p>
                )}
                <label className="block text-xs font-medium text-slate-500">
                  Reply
                  <textarea value={body ?? pending.draft.body} rows={8} onChange={(e) => setBody(e.target.value)}
                            className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm text-slate-800" data-testid="reply-body" />
                </label>
                {pending.draft.offered_slots.length > 0 && (
                  <div className="mt-2 text-xs text-slate-600">
                    <p className="font-medium">Interview slots offered (held tentatively on your calendar once sent):</p>
                    <ul className="list-disc pl-5">{pending.draft.offered_slots.map((s) => <li key={s.start_utc}>{when(s.start_local)}</li>)}</ul>
                  </div>
                )}
              </Card>
              <ApprovalPanel threadId={data.run_thread} kind="message" sendLabel="Approve & send"
                             edited={body !== null && body !== pending.draft.body ? { cover_letter: body } : null}
                             onDone={() => { setBody(null); mutate(); }} />
            </>
          ) : (
            <Card title="Reply"><p className="text-sm text-slate-500">{drafting ? "The Client Liaison is drafting a reply…" : "No reply waiting. Use “Draft a reply” to get a suggestion."}</p></Card>
          )}
        </div>
      </div>
    </>
  );
}
