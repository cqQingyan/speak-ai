from playwright.sync_api import sync_playwright

def verify_chat_interface():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the local Flask app
        page.goto("http://localhost:5000")

        # Verify title
        assert page.title() == "语音聊天助手"

        # Verify button exists
        btn = page.locator("#talk-btn")
        if btn.count() > 0:
            print("Talk button found.")

        # Verify initial AI message
        ai_msg = page.locator(".message.ai .bubble")
        print(f"Initial AI message: {ai_msg.first.inner_text()}")

        # Take screenshot
        page.screenshot(path="verification/chat_interface.png")
        print("Screenshot saved to verification/chat_interface.png")

        browser.close()

if __name__ == "__main__":
    verify_chat_interface()
