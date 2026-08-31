import { chromium } from "playwright";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const errors = [];
page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
page.on("pageerror", (err) => errors.push(String(err)));

await page.goto("http://localhost:8000/");
await page.waitForTimeout(1000);
await page.fill("input[type='text']", "admin");
await page.fill("input[type='password']", "admin123");
await page.click("button:has-text('登录')");
await page.waitForTimeout(2000);

// Get all clickable nav items
const navTexts = await page.evaluate(() => {
  const els = document.querySelectorAll("button, a, [role='button']");
  return Array.from(els).map(el => el.textContent.trim()).filter(t => t.length > 0 && t.length < 30);
});
console.log("Buttons/links:", JSON.stringify(navTexts));

await browser.close();
console.log("JS errors:", errors.length ? errors : "none");
