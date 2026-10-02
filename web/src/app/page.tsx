import { redirect } from "next/navigation";
import { auth, devLoginEnabled, signIn } from "@/auth";

export default async function Home() {
  const session = await auth();
  if (session?.user) redirect("/jobs");

  return (
    <div className="mx-auto max-w-md space-y-6 py-16 text-center">
      <h1 className="text-3xl font-bold">Land your next internship</h1>
      <p className="text-slate-600">
        New Montréal tech internships from company boards and Adzuna, in one place. Save postings, track them on a
        board, set reminders, and see how your search is going.
      </p>
      <form action={async () => { "use server"; await signIn("google", { redirectTo: "/jobs" }); }}>
        <button className="w-full rounded bg-slate-900 px-4 py-2 text-white hover:bg-slate-700">Continue with Google</button>
      </form>
      {devLoginEnabled && (
        <form
          action={async (fd: FormData) => { "use server"; await signIn("dev", { email: fd.get("email"), redirectTo: "/jobs" }); }}
          className="space-y-2 rounded border border-dashed p-4 text-left"
        >
          <p className="text-xs font-medium uppercase text-slate-500">Dev login (local only)</p>
          <input name="email" type="email" required defaultValue="dev@example.com" aria-label="Dev email" className="w-full rounded border px-3 py-1.5" />
          <button className="w-full rounded border px-3 py-1.5 hover:bg-slate-100">Dev login</button>
        </form>
      )}
    </div>
  );
}
