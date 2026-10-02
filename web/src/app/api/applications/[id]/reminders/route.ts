import { NextResponse } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";
import { apiUserId } from "@/lib/session";

const body = z.object({ dueAt: z.coerce.date(), note: z.string().max(500).default("") });

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const userId = await apiUserId();
  if (!userId) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const parsed = body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "bad request" }, { status: 400 });

  const { id } = await params;
  const app = await db.application.findFirst({ where: { id, userId } });
  if (!app) return NextResponse.json({ error: "not found" }, { status: 404 });

  const reminder = await db.reminder.create({ data: { applicationId: id, ...parsed.data } });
  return NextResponse.json(reminder, { status: 201 });
}
