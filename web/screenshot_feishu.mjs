import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

await page.goto("http://localhost:8000", { waitUntil: "networkidle" });
await page.waitForTimeout(500);

// Login
await page.locator('input[placeholder="用户名"]').fill("admin");
await page.locator('input[placeholder="密码"]').fill("admin123");
await page.locator('button:has-text("登录")').click();
await page.waitForTimeout(2500);
console.log("After login:", page.url());

// Find nav links
const navItems = await page.locator("nav a, nav button, .sidebar a, .sidebar button").allTextContents();
console.log("Nav:", navItems.join(" | "));

// Take screenshot of main view
await page.screenshot({ path: "/tmp/feishu_page1.png", fullPage: false });

// Search for feishu card
const feishuCard = await page.locator('h2:has-text("飞书")').count();
console.log("Feishu cards:", feishuCard);

// Take full screenshot
await page.screenshot({ path: "/tmp/feishu_page2.png", fullPage: true });

await browser.close();
console.log("Done");
