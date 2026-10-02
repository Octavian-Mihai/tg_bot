import { NextResponse } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";
import { apiUserId } from "@/lib/session";
import { STATUSES } from "@/lib/stats";

const patch = z.object({
  status: z.enum(STATUSES).optional(),
  position: z.number().finite().optional(),
  notes: z.string().max(5000).optional(),
});

type Ctx = { params: Promise<{ id: string }> };

export async function PATCH(req: Request, { params }: Ctx) {
  const userId = await apiUserId();
  if (!userId) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const parsed = patch.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "bad request" }, { status: 400 });

  const { id } = await params;
  const existing = await db.application.findFirst({ where: { id, userId } });
  if (!existing) return NextResponse.json({ error: "not found" }, { status: 404 });

  const { status } = parsed.data;
  const app = await db.application.update({
    where: { id },
    data: {
      ...parsed.data,
      // First time it leaves SAVED counts as the application date.
      ...(status && status !== "SAVED" && !existing.appliedAt ? { appliedAt: new Date() } : {}),
    },
  });
  return NextResponse.json(app);
}

export async function DELETE(_req: Request, { params }: Ctx) {
  const userId = await apiUserId();
  if (!userId) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const { id } = await params;
  const { count } = await db.application.deleteMany({ where: { id, userId } });
  return count ? new NextResponse(null, { status: 204 }) : NextResponse.json({ error: "not found" }, { status: 404 });
}
