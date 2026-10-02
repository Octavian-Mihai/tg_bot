"use client";
import { useState } from "react";

export function SaveButton({ jobId, initiallySaved }: { jobId: string; initiallySaved: boolean }) {
  const [saved, setSaved] = useState(initiallySaved);
  const [busy, setBusy] = useState(false);

  async function save() {
    setBusy(true);
    const res = await fetch("/api/applications", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ jobId }) });
    setBusy(false);
    if (res.ok) setSaved(true);
  }

  return saved ? (
    <span className="rounded bg-emerald-100 px-3 py-1 text-sm text-emerald-800">Saved ✓</span>
  ) : (
    <button onClick={save} disabled={busy} className="rounded border px-3 py-1 text-sm hover:bg-slate-100 disabled:opacity-50">
      Save
    </button>
  );
}
