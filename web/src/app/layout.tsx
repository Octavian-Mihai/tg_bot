import type { Metadata } from "next";
import Link from "next/link";
import { auth, signOut } from "@/auth";
import "./globals.css";

export const metadata: Metadata = { title: "Internbot", description: "Find internships and track your applications." };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <header className="border-b bg-white">
          <nav className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-3 text-sm">
            <Link href="/" className="text-lg font-semibold">Internbot</Link>
            {session?.user && (
              <>
                <Link href="/jobs" className="hover:underline">Jobs</Link>
                <Link href="/board" className="hover:underline">Board</Link>
                <Link href="/stats" className="hover:underline">Stats</Link>
                <span className="ml-auto text-slate-500">{session.user.email}</span>
                <form action={async () => { "use server"; await signOut({ redirectTo: "/" }); }}>
                  <button className="rounded border px-3 py-1 hover:bg-slate-100">Sign out</button>
                </form>
              </>
            )}
          </nav>
        </header>
        <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
