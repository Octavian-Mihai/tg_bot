import { NextResponse } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";
import { apiUserId } from "@/lib/session";

const body = z.object({ jobId: z.string().min(1) });

/** Save a job to the board (idempotent). */
export async function POST(req: Request) {
  const userId = await apiUserId();
  if (!userId) return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  const parsed = body.safeParse(await req.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: "bad request" }, { status: 400 });

  const job = await db.job.findUnique({ where: { id: parsed.data.jobId } });
  if (!job) return NextResponse.json({ error: "job not found" }, { status: 404 });

  const last = await db.application.findFirst({ where: { userId, status: "SAVED" }, orderBy: { position: "desc" } });
  const app = await db.application.upsert({
    where: { userId_jobId: { userId, jobId: job.id } },
    update: {},
    create: { userId, jobId: job.id, position: (last?.position ?? 0) + 1 },
  });
  return NextResponse.json(app, { status: 201 });
}
