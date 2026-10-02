import { expect, type Page } from "@playwright/test";

let n = 0;
export const uniqueEmail = () => `user${Date.now()}${n++}@example.com`;

export async function login(page: Page, email = uniqueEmail()) {
  await page.goto("/");
  await page.getByLabel("Dev email").fill(email);
  await page.getByRole("button", { name: "Dev login" }).click();
  await expect(page).toHaveURL(/\/jobs/);
  return email;
}

export async function saveJob(page: Page, title: string) {
  const row = page.getByTestId("job-row").filter({ hasText: title });
  await row.getByRole("button", { name: "Save" }).click();
  await expect(row.getByText("Saved ✓")).toBeVisible();
}
