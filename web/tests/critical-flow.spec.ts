import { expect, test } from "@playwright/test";

test("industrial anomaly flow exposes model selection, replay and agent trace", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "产线异常态势" })).toBeVisible();
  await expect(page.getByLabel("检测模型")).toHaveValue("EfficientAD · MVTEC pretrained");
  await expect(page.getByLabel("检测对象 / 数据集")).toHaveValue("MVTec AD · Hazelnut");

  await page.getByRole("button", { name: "运行全链路演示" }).click();
  await expect(page.getByText("全链路调研已完成 · 等待人工决策")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("heading", { name: "Agent 自动调研轨迹" })).toBeVisible();
  await expect(page.getByText("不暴露模型隐藏思维链")).toBeVisible();

  await page.getByRole("button", { name: "系统运行" }).click();
  await expect(page.getByText("Worker 健康度")).toBeVisible();
  await expect(page.getByText("investigation-worker")).toBeVisible();

  await page.getByRole("button", { name: "模型评估" }).click();
  await expect(page.getByText("配置对比")).toBeVisible();
  await expect(page.getByText("潜在价值测算")).toBeVisible();
});

test("monitoring controls and event navigation are actionable", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "查看全部" }).click();
  await expect(page.getByRole("heading", { name: "异常事件中心" })).toBeVisible();

  await page.getByRole("button", { name: "查看事件详情 EVT-0823-041" }).click();
  await expect(page.getByRole("dialog", { name: "异常事件详情" })).toBeVisible();
  await page.getByRole("button", { name: "查看相关 Case" }).click();
  await expect(page.locator("h1", { hasText: "质量 Case" })).toBeVisible();

  await page.getByRole("button", { name: "实时监控" }).click();
  await page.getByLabel("监控布局").selectOption("heatmap");
  await expect(page.getByLabel("监控布局")).toHaveValue("heatmap");
  await page.getByRole("button", { name: "24H" }).click();
  await expect(page.getByRole("button", { name: "24H" })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: "查看建议排查方案" }).click();
  await expect(page.locator("h1", { hasText: "待人工决策" })).toBeVisible();
});
