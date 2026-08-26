import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

await page.goto("http://localhost:8000", { waitUntil: "networkidle" });
await page.waitForTimeout(500);

// Login
await page.locator('input[placeholder="用户名"]').fill("admin");
await page.locator('input[placeholder="密码"]').fill("admin123");
await page.locator('button:has-text("登录")').click();
await page.waitForTimeout(3000);

// Extract the feishu card content
const feishuSection = page.locator('section:has(h2:has-text("飞书"))');
const feishuText = await feishuSection.innerText();
console.log("=== 飞书卡片内容 ===");
console.log(feishuText);

// Count messages
const msgCount = await page.locator('.feishu-msg').count();
console.log("\n消息条数:", msgCount);

// List quick buttons
const quickBtns = await page.locator('.feishu-quick-bar button').allTextContents();
console.log("快捷按钮:", quickBtns.join(" | "));

// Test clicking "获取策略" button
console.log("\n=== 测试点击「获取策略」按钮 ===");
await page.locator('.feishu-quick-bar button:has-text("获取策略")').click();
await page.waitForTimeout(2000);

// Get reply
const replyText = await page.locator('.feishu-reply').innerText().catch(() => "无回复");
console.log("回复:", replyText);

// Test clicking "回传示例" button
console.log("\n=== 测试点击「回传示例」按钮 ===");
await page.locator('.feishu-quick-bar button:has-text("回传示例")').click();
await page.waitForTimeout(2000);
const replyText2 = await page.locator('.feishu-reply').innerText().catch(() => "无回复");
console.log("回复:", replyText2);

// Take final screenshot
await page.screenshot({ path: "/tmp/feishu_final.png", fullPage: false });

await browser.close();
console.log("\n=== 验证完成 ===");
