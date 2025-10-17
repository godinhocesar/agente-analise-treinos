import asyncio
from playwright.async_api import async_playwright

async def main():
    print("Starting verification script...")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        print("Waiting for application to start...")
        await asyncio.sleep(15)
        print("Navigating to application...")
        await page.goto("http://localhost:8501")
        print("Taking screenshot...")
        await page.screenshot(path="verification.png")
        await browser.close()
        print("Verification script finished.")

asyncio.run(main())