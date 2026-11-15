"use client";

// Agent run viewer: live node-by-node progress streamed from LangGraph, with a link to the full trace.
import Link from "next/link";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { StatusBadge } from "@/components/badges";
import { RunTimeline } from "@/components/timeline";
import { Button, Card, ErrorState, PageHeader, Spinner, Stat } from "@/components/ui";
import { endpoints } from "@/lib/api/endpoints";
import type { BidState } from "@/lib/types";

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const threadId = decodeURIComponent(params.id);
  const { data, error, isLoading, mutate } = useSWR(["run", threadId], () => endpoints.run(threadId));
  if (isLoading) return <Spinner />;
  if (error) return <ErrorState error={error} retry={() => mutate()} />;
  if (!data) return null;
  const s = data.state as BidState;
  const jobId = threadId.startsWith("bid:") ? threadId.split(":")[2] : null;
  return (
    <>
      <PageHeader
        title={s.job?.title ?? threadId}
        subtitle={<span className="flex flex-wrap items-center gap-2"><StatusBadge status={data.status} />{data.status_reason}</span>}
        actions={
          <>
            {data.pending_approval && jobId && <Link href={`/studio/${jobId}`}><Button>Review</Button></Link>}
            {data.trace_url && <a href={data.trace_url} target="_blank" rel="noreferrer"><Button variant="secondary">Open full trace</Button></a>}
          </>
        }
      />
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Steps" value={s.steps ?? 0} />
        <Stat label="Tokens" value={(s.tokens ?? 0).toLocaleString()} />
        <Stat label="Trace id" value={<span className="break-all text-sm">{data.trace_id ?? "—"}</span>} />
        <Stat label="Kind" value={data.kind} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Live progress"><RunTimeline threadId={threadId} saved={data.events} onFinished={() => mutate()} /></Card>
        <Card title="Errors">
          {s.errors?.length ? <ul className="list-disc pl-5 text-sm text-rose-700">{s.errors.map((e) => <li key={e}>{e}</li>)}</ul> : <p className="text-sm text-slate-500">None.</p>}
        </Card>
      </div>
    </>
  );
}
