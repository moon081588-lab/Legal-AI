import { expect, test } from "@playwright/test";

test("landing page renders with disclaimer and quick exit", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Legal-AI/ })).toBeVisible();
  await expect(page.getByText("법률 자문이 아니며")).toBeVisible();
  await expect(page.getByRole("button", { name: /빠른 나가기/ })).toBeVisible();
});

test("asking a question streams an answer with sources", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("법률 관련 궁금한 점을 물어보세요").fill("전세 보증금을 못 돌려받고 있어요");
  await page.getByRole("button", { name: "질문" }).click();
  await expect(page.getByText(/근거 조문 \d+건 보기/)).toBeVisible({ timeout: 15000 });
  await expect(page.locator(".msg.bot").last()).toContainText("법률 자문이 아닙니다", { timeout: 15000 });
});

test("checklist panel opens with urgent CCTV item", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /증거 체크리스트/ }).click();
  await page.getByRole("button", { name: "폭행·상해" }).click();
  await expect(page.getByText(/CCTV 보존 요청/)).toBeVisible();
});

test("procedure navigator shows 불송치 이의신청 stage", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /절차 안내/ }).click();
  await page.getByRole("button", { name: /불송치에 대한 이의신청/ }).click();
  await expect(page.getByText("제245조의7")).toBeVisible();
});

test("journal entry persists across reloads (IndexedDB)", async ({ page }) => {
  await page.goto("/journal");
  await page.locator('input[type="date"]').fill("2026-08-01");
  await page.getByPlaceholder(/제목/).fill("테스트 기록");
  await page.getByRole("button", { name: "기록 추가" }).click();
  await expect(page.getByText("테스트 기록")).toBeVisible();
  await page.reload();
  await expect(page.getByText("테스트 기록")).toBeVisible();
});

test("journal offers encrypted backup and restore", async ({ page }) => {
  await page.goto("/journal");
  await page.getByRole("button", { name: /백업·복원/ }).click();
  await expect(page.getByPlaceholder(/비워 두면/)).toBeVisible();
  await expect(page.getByRole("button", { name: /백업 파일 복원/ })).toBeVisible();
});

test("static panels still work when the API is unreachable", async ({ page, context }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /증거 체크리스트/ }).click();
  await page.getByRole("button", { name: "폭행·상해" }).click();
  await expect(page.getByText(/CCTV 보존 요청/)).toBeVisible(); // primed the cache

  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("heading", { name: /Legal-AI/ })).toBeVisible();
  await expect(page.getByText(/오프라인 상태입니다/)).toBeVisible();
  await context.setOffline(false);
});
