import asyncio
from playwright.async_api import async_playwright

async def main():
    print("Launching browser with anti-detection flags...")
    async with async_playwright() as p:
        print("Opening persistent context in ./chrome_data ...")
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./chrome_data",
            channel="chrome",  # Forces Playwright to use your actual installed Google Chrome
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],  # Hides the webdriver flag
            ignore_default_args=["--enable-automation"],  # Removes the "Chrome is being controlled" banner
            viewport={"width": 1280, "height": 720}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        print("Navigating to Google Photos...")
        await page.goto("https://photos.google.com/login")
        
        print("\n*** PLEASE LOG IN NOW ***")
        print("You have 3 minutes to enter your credentials.")
        print("Once you are fully logged in and see your photos, you can close the terminal with Ctrl+C or wait.")
        
        try:
            # Wait for 3 minutes (180,000 milliseconds)
            await page.wait_for_timeout(180000)
        except Exception:
            pass
            
        print("\nClosing and saving session...")
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())