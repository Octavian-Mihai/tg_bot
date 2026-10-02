import { NextResponse } from "next/server";
import { db } from "@/lib/db";
import { apiUserId } from "@/lib/session";

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userId = await apiUserId();
  if (!userId) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const { id } = await params;
  const { count } = await db.reminder.deleteMany({ where: { id, application: { userId } } });
  return count ? new NextResponse(null, { status: 204 }) : NextResponse.json({ error: "not found" }, { status: 404 });
}
