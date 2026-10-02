import { redirect } from "next/navigation";
import { auth } from "@/auth";

export async function requireUser() {
  const session = await auth();
  if (!session?.user?.id) redirect("/");
  return session.user;
}

/** For API routes: returns the user id or null. */
export async function apiUserId(): Promise<string | null> {
  const session = await auth();
  return session?.user?.id ?? null;
}
