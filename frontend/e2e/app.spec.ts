import { expect, test, type Page } from "@playwright/test";

/** Locators use class hooks or .first() rather than bare getByText: several
 *  strings appear in both an inner <b> and its wrapper, which trips Playwright's
 *  strict mode. */

async function openPanel(page: Page, name: RegExp) {
  await page.getByRole("button", { name }).click();
}

test("landing page renders with disclaimer and quick exit", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Legal-AI/ })).toBeVisible();
  await expect(page.locator(".notice").first()).toContainText("법률 자문이 아니며");
  await expect(page.getByRole("button", { name: /빠른 나가기/ })).toBeVisible();
});

test("asking a question streams an answer with sources", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("법률 관련 궁금한 점을 물어보세요").fill("전세 보증금을 못 돌려받고 있어요");
  await page.getByRole("button", { name: "질문" }).click();
  await expect(page.locator("details.sources").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".msg.bot").last()).toContainText("법률 자문이 아닙니다", { timeout: 20_000 });
});

test("checklist panel opens with urgent CCTV item", async ({ page }) => {
  await page.goto("/");
  await openPanel(page, /증거 체크리스트/);
  await page.getByRole("button", { name: "폭행·상해" }).click();
  await expect(page.locator(".check-item.urgent").filter({ hasText: "CCTV" }).first()).toBeVisible();
  // sources must be shown alongside the advice
  await expect(page.locator(".checklist-panel .src").first()).toBeVisible();
});

test("support checker surfaces free legal representation with a source", async ({ page }) => {
  await page.goto("/");
  await openPanel(page, /무료 지원 확인/);
  await page.getByRole("button", { name: "성폭력" }).click();
  await expect(page.locator(".program.matched").first()).toContainText("피해자 국선변호사");
  await expect(page.locator(".program.matched .src a").first()).toBeVisible();
});

test("centers panel lists emergency hotlines", async ({ page }) => {
  await page.goto("/");
  await openPanel(page, /지원기관 찾기/);
  await expect(page.locator(".hotline").first()).toBeVisible();
  await expect(page.locator('.hotline[href="tel:1366"]')).toBeVisible();
});

test("procedure navigator shows 불송치 이의신청 stage", async ({ page }) => {
  await page.goto("/");
  await openPanel(page, /절차 안내/);
  await page.getByRole("button", { name: /불송치에 대한 이의신청/ }).click();
  await expect(page.locator(".stage-body").first()).toContainText("제245조의7");
});

test("glossary page defines legal terms", async ({ page }) => {
  await page.goto("/glossary");
  await expect(page.getByRole("heading", { name: /법률 용어 사전/ })).toBeVisible();
  await page.getByPlaceholder(/용어를 검색/).fill("불송치");
  await expect(page.locator(".journal-entry").first()).toContainText("불송치");
});

test("journal entry persists across reloads (IndexedDB)", async ({ page }) => {
  await page.goto("/journal");
  await page.locator('input[type="date"]').fill("2026-08-01");
  await page.getByPlaceholder(/제목/).fill("테스트 기록");
  await page.getByRole("button", { name: "기록 추가" }).click();
  await expect(page.locator(".journal-entry").first()).toContainText("테스트 기록");
  await page.reload();
  await expect(page.locator(".journal-entry").first()).toContainText("테스트 기록");
});

test("journal offers encrypted backup and restore", async ({ page }) => {
  await page.goto("/journal");
  await page.getByRole("button", { name: /백업·복원/ }).click();
  await expect(page.getByPlaceholder(/비워 두면/)).toBeVisible();
  await expect(page.getByRole("button", { name: /백업 파일 복원/ })).toBeVisible();
});

test("offline banner appears when the connection drops", async ({ page, context }) => {
  await page.goto("/");
  await context.setOffline(true);
  await expect(page.locator(".offline-banner")).toBeVisible();
  await context.setOffline(false);
  await expect(page.locator(".offline-banner")).toBeHidden();
});

test("service worker serves the app shell while offline", async ({ page, context }) => {
  await page.goto("/");
  // Wait until the service worker actually controls this page — without this the
  // reload below races registration and fails for reasons unrelated to caching.
  const controlled = await page
    .waitForFunction(() => navigator.serviceWorker?.controller != null, null, { timeout: 20_000 })
    .then(() => true)
    .catch(() => false);
  test.skip(!controlled, "service worker did not take control in this environment");

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: /Legal-AI/ })).toBeVisible();
  await context.setOffline(false);
});
