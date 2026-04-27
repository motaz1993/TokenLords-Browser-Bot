"""BrowserController - Handles Playwright page interactions, navigation, retries."""
import asyncio
from typing import Optional
from playwright.async_api import Page, Browser, async_playwright


class BrowserController:
    """Handles all browser interactions with retry logic and error handling."""
    
    BASE_URL = "https://game.tokenlordsrpg.com"
    
    def __init__(self):
        self.page: Optional[Page] = None
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.is_connected = False
    
    async def connect(self, cdp_url: str = "http://localhost:9222") -> bool:
        """Connect to Edge via CDP."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
            contexts = self.browser.contexts
            if contexts:
                pages = contexts[0].pages
                if pages:
                    self.page = pages[0]
                    self.is_connected = True
                    return True
            return False
        except Exception as e:
            print(f"[Browser] Connection error: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from browser with graceful cleanup."""
        try:
            # Don't close the page - it's the user's browser, not ours
            # Just clear our reference
            self.page = None
            if self.browser:
                # Close the browser connection (not the actual browser)
                try:
                    await self.browser.close()
                except:
                    pass
                self.browser = None
            if self.playwright:
                # Finally stop playwright
                try:
                    await self.playwright.stop()
                except:
                    pass
                self.playwright = None
        except Exception as e:
            print(f"[Browser] Disconnect error: {e}")
        finally:
            self.is_connected = False
            self.page = None
            self.browser = None
            self.playwright = None
    
    async def navigate(self, path: str, timeout: int = 10000, wait_for_load: bool = True) -> bool:
        """Navigate to a game page with retry logic."""
        if not self.page:
            return False
        
        url = f"{self.BASE_URL}/{path}" if not path.startswith("http") else path
        
        # Check if already on this page
        if self.page.url == url:
            return True
        
        for attempt in range(3):
            try:
                await self.page.goto(url, timeout=timeout)
                if wait_for_load:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
                    await asyncio.sleep(0.5)
                return True
            except Exception as e:
                print(f"[Browser] Navigate error (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        return False
    
    async def click(self, selector: str, force: bool = False, timeout: int = 5000) -> bool:
        """Click element with retry."""
        if not self.page:
            return False
        
        try:
            loc = self.page.locator(selector).first
            if await loc.count() == 0:
                return False
            
            if force:
                await loc.evaluate("node => node.click()")
            else:
                await loc.click(timeout=timeout)
            return True
        except Exception as e:
            print(f"[Browser] Click error: {e}")
            return False
    
    async def click_fast(self, selector: str, force: bool = False, timeout: int = 1500) -> bool:
        """Fast click for battle operations - shorter timeout."""
        if not self.page:
            return False
        
        try:
            loc = self.page.locator(selector).first
            if await loc.count() == 0:
                return False
            
            if force:
                await loc.evaluate("node => node.click()")
            else:
                await loc.click(timeout=timeout)
            return True
        except Exception as e:
            print(f"[Browser] Fast click error: {e}")
            return False
    
    async def click_by_text(self, text: str, element: str = "button", timeout: int = 5000) -> bool:
        """Click element by text content."""
        if not self.page:
            return False
        
        try:
            loc = self.page.locator(f"{element}:has-text('{text}')").first
            if await loc.count() > 0:
                await loc.click(timeout=timeout)
                return True
            return False
        except Exception as e:
            print(f"[Browser] Click by text error: {e}")
            return False
    
    async def get_text(self, selector: str, timeout: int = 2000) -> Optional[str]:
        """Get text content of element."""
        if not self.page:
            return None
        
        try:
            loc = self.page.locator(selector).first
            if await loc.count() > 0:
                return await loc.inner_text(timeout=timeout)
            return None
        except:
            return None
    
    async def wait_for_selector(self, selector: str, timeout: int = 5000) -> bool:
        """Wait for element to appear."""
        if not self.page:
            return False
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except:
            return False
    
    async def is_visible(self, selector: str) -> bool:
        """Check if element is visible."""
        if not self.page:
            return False
        
        try:
            loc = self.page.locator(selector).first
            if await loc.count() > 0:
                return await loc.is_visible()
            return False
        except:
            return False
    
    async def count_elements(self, selector: str) -> int:
        """Count elements matching selector."""
        if not self.page:
            return 0
        
        try:
            return await self.page.locator(selector).count()
        except:
            return 0
    
    async def handle_landing_page(self) -> bool:
        """Auto-recover from landing page."""
        if not self.page:
            return False
        
        try:
            body_class = await self.page.evaluate("() => document.body.className")
            if "landing-page" not in body_class:
                return False
            
            print("[Browser] Landing page detected, attempting recovery...")
            await asyncio.sleep(5)
            
            # Try to click Enter Realm
            for selector in ["button:has-text('Enter Realm')", ".btn-hero-primary", ".btn-final-cta"]:
                if await self.click(selector):
                    print("[Browser] Clicked Enter Realm")
                    await asyncio.sleep(8)
                    await self.page.wait_for_load_state("domcontentloaded")
                    return True
            return False
        except:
            return False
    
    async def dismiss_energy_popup(self) -> bool:
        """Dismiss low energy popup."""
        if not self.page:
            return False
        
        try:
            popup = self.page.locator(".low-energy-popup-overlay")
            if await popup.count() > 0:
                btn = self.page.locator(".low-energy-popup-btn.secondary").first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(0.5)
                    return True
            return False
        except:
            return False
    
    async def dismiss_easter_popup(self) -> bool:
        """Dismiss Easter/holiday event popup."""
        if not self.page:
            return False
        
        try:
            # Try multiple possible selectors for close buttons
            close_selectors = [
                ".easter-popup-overlay .close-btn",
                ".easter-popup-overlay .dismiss-btn",
                ".holiday-popup-overlay .close-btn",
                ".event-popup-overlay .close-btn",
                ".popup-overlay .close",
                "[class*='popup'] button[class*='close']",
                "[class*='popup'] .btn-close",
            ]
            
            for selector in close_selectors:
                btn = self.page.locator(selector).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.5)
                    print("[Browser] Dismissed Easter/holiday popup")
                    return True
            
            # If no close button found, try pressing Escape key
            await self.page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            return True
        except:
            return False
    
    async def is_maintenance(self) -> bool:
        """Check if game is in maintenance mode."""
        if not self.page:
            return False
        
        try:
            count = await self.count_elements("text=Maintenance Mode")
            count += await self.count_elements("text=We'll Be Right Back")
            html = await self.page.content()
            return count > 0 or "maintenancePulse" in html
        except:
            return False
    
    async def safe_action(self, action_func, max_retries: int = 3, delay: float = 1.0):
        """Execute action with retries."""
        for attempt in range(max_retries):
            try:
                return await action_func()
            except Exception as e:
                print(f"[Browser] Action error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
        return None
    
    def is_on_page(self, path: str) -> bool:
        """Check if currently on a specific page."""
        if not self.page:
            return False
        return path in self.page.url
