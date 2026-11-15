"use client";

// Sign in and onboarding (create an account and pick a portfolio persona).
import { useRouter } from "next/navigation";
import { useState } from "react";
import { endpoints } from "@/lib/api/endpoints";
import { Button, Card } from "@/components/ui";

const PERSONAS = [
  { id: "data_analyst", label: "Data analyst", hint: "Power BI, SQL, Excel reporting" },
  { id: "ml_engineer", label: "ML engineer", hint: "NLP, LLM apps, ML pipelines" },
  { id: "fullstack_dev", label: "Full-stack developer", hint: "React, Next.js, Node, Django" },
] as const;

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [persona, setPersona] = useState<(typeof PERSONAS)[number]["id"]>("data_analyst");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "signin") await endpoints.login(email, password);
      else await endpoints.register({ email, password, name, persona });
      router.replace("/inbox");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(false);
    }
  }

  const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm";
  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <div className="w-full max-w-md">
        <h1 className="mb-1 text-2xl font-bold">GigBid</h1>
        <p className="mb-6 text-sm text-slate-600">
          Finds freelance jobs, checks them, and drafts proposals backed by your real work. Nothing is sent without
          your approval.
        </p>
        <Card>
          <div role="tablist" className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1 text-sm">
            {(["signin", "register"] as const).map((m) => (
              <button
                key={m}
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={`rounded-md py-1.5 font-medium ${mode === m ? "bg-white shadow-sm" : "text-slate-600"}`}
              >
                {m === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>
          <form onSubmit={submit} className="space-y-3">
            {mode === "register" && (
              <label className="block text-sm font-medium">
                Name
                <input className={input} value={name} onChange={(e) => setName(e.target.value)} required />
              </label>
            )}
            <label className="block text-sm font-medium">
              Email
              <input className={input} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </label>
            <label className="block text-sm font-medium">
              Password
              <input className={input} type="password" autoComplete={mode === "signin" ? "current-password" : "new-password"}
                     minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} required />
            </label>
            {mode === "register" && (
              <fieldset>
                <legend className="text-sm font-medium">Your portfolio</legend>
                <p className="mb-2 text-xs text-slate-500">
                  Pick a demo persona (synthetic CV, case studies, repos and past proposals). Connecting your own
                  portfolio and Upwork account comes next, in Settings.
                </p>
                <div className="space-y-2">
                  {PERSONAS.map((p) => (
                    <label key={p.id} className="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-200 p-2 text-sm has-[:checked]:border-slate-900">
                      <input type="radio" name="persona" value={p.id} checked={persona === p.id} onChange={() => setPersona(p.id)} className="mt-1" />
                      <span><span className="font-medium">{p.label}</span><span className="block text-xs text-slate-500">{p.hint}</span></span>
                    </label>
                  ))}
                </div>
              </fieldset>
            )}
            {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
            </Button>
          </form>
        </Card>
        <p className="mt-4 text-center text-xs text-slate-500">Reviewers: use the login sent with the submission.</p>
      </div>
    </main>
  );
}
