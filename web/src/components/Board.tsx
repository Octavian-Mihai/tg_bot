"use client";
import { useState } from "react";
import {
  DndContext, DragOverlay, PointerSensor, closestCorners, useDroppable, useSensor, useSensors,
  type DragEndEvent, type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { STATUSES, type StatusName } from "@/lib/stats";
import { positionAt } from "@/lib/position";

export interface CardData {
  id: string;
  status: StatusName;
  position: number;
  title: string;
  company: string;
  url: string;
  reminders: { id: string; dueAt: string; note: string }[];
}

const LABELS: Record<StatusName, string> = {
  SAVED: "Saved", APPLIED: "Applied", OA: "OA", INTERVIEW: "Interview", OFFER: "Offer", REJECTED: "Rejected",
};

async function api(path: string, method: string, body?: unknown) {
  const res = await fetch(path, { method, headers: { "content-type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(`${method} ${path} failed (${res.status})`);
  return res.status === 204 ? null : res.json();
}

export function Board({ initial }: { initial: CardData[] }) {
  const [cards, setCards] = useState(initial);
  const [dragging, setDragging] = useState<CardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const column = (s: StatusName, list = cards) => list.filter((c) => c.status === s).sort((a, b) => a.position - b.position);

  /** Optimistically move a card; roll back if the server rejects it. */
  async function move(id: string, status: StatusName, index: number) {
    const snapshot = cards;
    const others = column(status).filter((c) => c.id !== id);
    const position = positionAt(others.map((c) => c.position), Math.min(index, others.length));
    setCards((cs) => cs.map((c) => (c.id === id ? { ...c, status, position } : c)));
    try {
      await api(`/api/applications/${id}`, "PATCH", { status, position });
      setError(null);
    } catch {
      setCards(snapshot);
      setError("Couldn't save that move — reverted.");
    }
  }

  function onDragEnd(e: DragEndEvent) {
    setDragging(null);
    const { active, over } = e;
    if (!over) return;
    const overId = String(over.id);
    const overCard = cards.find((c) => c.id === overId);
    const status = overCard ? overCard.status : (overId as StatusName);
    if (!STATUSES.includes(status)) return;
    const target = column(status).filter((c) => c.id !== active.id);
    const index = overCard ? Math.max(0, target.findIndex((c) => c.id === overId)) : target.length;
    void move(String(active.id), status, index);
  }

  async function remove(id: string) {
    const snapshot = cards;
    setCards((cs) => cs.filter((c) => c.id !== id));
    try { await api(`/api/applications/${id}`, "DELETE"); } catch { setCards(snapshot); setError("Couldn't remove that card."); }
  }

  async function addReminder(id: string, dueAt: string, note: string) {
    try {
      const r = await api(`/api/applications/${id}/reminders`, "POST", { dueAt, note });
      setCards((cs) => cs.map((c) => (c.id === id ? { ...c, reminders: [...c.reminders, { id: r.id, dueAt: r.dueAt, note: r.note }] } : c)));
    } catch { setError("Couldn't add that reminder."); }
  }

  async function removeReminder(cardId: string, reminderId: string) {
    try {
      await api(`/api/reminders/${reminderId}`, "DELETE");
      setCards((cs) => cs.map((c) => (c.id === cardId ? { ...c, reminders: c.reminders.filter((r) => r.id !== reminderId) } : c)));
    } catch { setError("Couldn't remove that reminder."); }
  }

  const props = { move, remove, addReminder, removeReminder };

  return (
    <div className="space-y-3">
      {error && <p role="alert" className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {cards.length === 0 && <p className="text-slate-500">Nothing here yet — save some postings from the Jobs page.</p>}
      <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={(e: DragStartEvent) => setDragging(cards.find((c) => c.id === e.active.id) ?? null)} onDragEnd={onDragEnd} onDragCancel={() => setDragging(null)}>
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          {STATUSES.map((s) => (
            <Column key={s} status={s} cards={column(s)} {...props} />
          ))}
        </div>
        <DragOverlay>{dragging && <CardBody card={dragging} {...props} overlay />}</DragOverlay>
      </DndContext>
    </div>
  );
}

type Handlers = {
  move: (id: string, s: StatusName, i: number) => void;
  remove: (id: string) => void;
  addReminder: (id: string, dueAt: string, note: string) => void;
  removeReminder: (cardId: string, reminderId: string) => void;
};

function Column({ status, cards, ...h }: { status: StatusName; cards: CardData[] } & Handlers) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <section ref={setNodeRef} data-testid={`col-${status}`} className={`min-h-40 rounded border p-2 ${isOver ? "bg-slate-200" : "bg-slate-100"}`}>
      <h2 className="mb-2 flex justify-between px-1 text-sm font-semibold">
        {LABELS[status]} <span className="text-slate-500">{cards.length}</span>
      </h2>
      <SortableContext items={cards.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        <div className="space-y-2">
          {cards.map((c) => (
            <SortableCard key={c.id} card={c} {...h} />
          ))}
        </div>
      </SortableContext>
    </section>
  );
}

function SortableCard({ card, ...h }: { card: CardData } & Handlers) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: card.id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.4 : 1 }}>
      <CardBody card={card} {...h} dragHandle={{ ...attributes, ...listeners }} />
    </div>
  );
}

function CardBody({ card, move, remove, addReminder, removeReminder, dragHandle, overlay }: { card: CardData; dragHandle?: object; overlay?: boolean } & Handlers) {
  const [open, setOpen] = useState(false);
  const [due, setDue] = useState("");
  const [note, setNote] = useState("");

  return (
    <article data-testid="card" className={`rounded border bg-white p-2 text-sm shadow-sm ${overlay ? "shadow-lg" : ""}`}>
      <div className="flex items-start gap-1">
        <button aria-label="Drag" className="cursor-grab px-1 text-slate-400 touch-none" {...dragHandle}>⠿</button>
        <div className="min-w-0 flex-1">
          <a href={card.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">{card.title}</a>
          <div className="text-slate-600">{card.company}</div>
        </div>
      </div>
      {!overlay && (
        <>
          <div className="mt-2 flex items-center gap-1">
            <select aria-label="Status" value={card.status} onChange={(e) => move(card.id, e.target.value as StatusName, Number.MAX_SAFE_INTEGER)} className="min-w-0 flex-1 rounded border px-1 py-0.5 text-xs">
              {STATUSES.map((s) => <option key={s} value={s}>{LABELS[s]}</option>)}
            </select>
            <button onClick={() => setOpen(!open)} className="rounded border px-1.5 py-0.5 text-xs hover:bg-slate-100" aria-label="Reminders">⏰ {card.reminders.length || ""}</button>
            <button onClick={() => remove(card.id)} className="rounded border px-1.5 py-0.5 text-xs hover:bg-red-50" aria-label="Remove">✕</button>
          </div>
          {open && (
            <div className="mt-2 space-y-1 border-t pt-2">
              {card.reminders.map((r) => (
                <div key={r.id} className="flex items-center justify-between text-xs">
                  <span>{new Date(r.dueAt).toLocaleDateString()} {r.note && `— ${r.note}`}</span>
                  <button onClick={() => removeReminder(card.id, r.id)} aria-label="Delete reminder">✕</button>
                </div>
              ))}
              <form
                onSubmit={(e) => { e.preventDefault(); if (due) { addReminder(card.id, new Date(due).toISOString(), note); setDue(""); setNote(""); } }}
                className="flex flex-wrap gap-1"
              >
                <input type="date" value={due} onChange={(e) => setDue(e.target.value)} required aria-label="Reminder date" className="rounded border px-1 text-xs" />
                <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note" aria-label="Reminder note" className="min-w-0 flex-1 rounded border px-1 text-xs" />
                <button className="rounded border px-2 text-xs hover:bg-slate-100">Add</button>
              </form>
            </div>
          )}
        </>
      )}
    </article>
  );
}
