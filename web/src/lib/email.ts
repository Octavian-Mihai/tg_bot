/** Sends via Resend's HTTP API. Without RESEND_API_KEY it logs instead, so local dev needs no account. */
export async function sendEmail(to: string, subject: string, text: string): Promise<void> {
  const key = process.env.RESEND_API_KEY;
  if (!key) {
    console.log(`[email:dev] to=${to} subject=${JSON.stringify(subject)}\n${text}`);
    return;
  }
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { authorization: `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({ from: process.env.REMINDER_FROM ?? "Internbot <onboarding@resend.dev>", to, subject, text }),
  });
  if (!res.ok) throw new Error(`email send failed (HTTP ${res.status})`);
}
