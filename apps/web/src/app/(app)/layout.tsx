import { Suspense } from "react";
import { AppShell } from "@/components/shell";
import { Spinner } from "@/components/ui";

// The shell and pages read the URL (usePathname / useParams), which is only known at request time.
// Suspense lets Next.js prerender a static loading shell and stream the rest in.
export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense fallback={<div className="flex min-h-screen items-center justify-center"><Spinner /></div>}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
