"""BusinessWorker - Executes business-related actions."""
import asyncio
import time
import random


class BusinessWorker:
    """Stateless business executor - follows Brain commands."""
    
    MATERIAL_NAMES = ["Wood", "Wheat", "Rock", "Food", "Cloth"]
    
    def __init__(self, browser, game_state, settings, brain=None):
        self.browser = browser
        self.state = game_state
        self.settings = settings
        self.brain = brain
        
        # Timer for auto-collection (single Collect All)
        self.next_collect_at: float = 0
        
        # Temporary interval override (for testing, not saved to settings)
        self.custom_collect_interval: int = None
    
    def _jitter_schedule(self, minutes: int) -> float:
        """Calculate next collection time with jitter."""
        base_sec = minutes * 60
        jitter = random.randint(-120, 120)
        return time.time() + max(60, base_sec + jitter)
    
    def schedule_collect(self):
        """Schedule next Collect All collection."""
        # Use custom interval if set (for testing), otherwise use settings
        if self.custom_collect_interval is not None:
            interval = self.custom_collect_interval
        else:
            interval = self.settings.get("business.collect_interval_min", 30)
        self.next_collect_at = self._jitter_schedule(interval)
    
    def should_collect(self) -> bool:
        """Check if Collect All should be used."""
        auto_enabled = self.settings.get("business.auto_collect", False)
        now = time.time()
        
        if not auto_enabled:
            return False
        
        # If timer was never set (0), allow immediate collection
        # This handles first-time enablement
        if self.next_collect_at == 0:
            print("[BusinessWorker] Timer never set, allowing immediate collection")
            return True
        
        # Check if timer has expired
        if now < self.next_collect_at:
            return False
        
        # Check if there's anything to collect
        stored_bronze = self.state.business_stored.get("bronze", 0)
        has_bronze = stored_bronze > 0
        
        has_materials = False
        for mat in self.MATERIAL_NAMES:
            if self.state.business_stored.get(mat, 0) > 0:
                has_materials = True
                break
        
        if has_bronze or has_materials:
            print(f"[BusinessWorker] Ready to collect: bronze={stored_bronze}, materials={has_materials}")
            return True
        
        return False
    
    def get_collect_countdown(self) -> int:
        """Get countdown in seconds for Collect All."""
        if not self.settings.get("business.auto_collect", False):
            return -1  # -1 means off
        
        return max(0, int(self.next_collect_at - time.time()))
    
    async def collect_all(self) -> bool:
        """Collect all using Collect All button."""
        try:
            # Ensure on business page
            if not self.browser.is_on_page("businesses"):
                if not await self.browser.navigate("businesses"):
                    return False
                await asyncio.sleep(1)
            
            # Try to find and click Collect All button
            btn = self.browser.page.locator(".b3d-fab.b3d-fab--pulse").first
            if await btn.count() == 0:
                # Fallback to text-based locator
                btn = self.browser.page.locator("button:has-text('Collect All')").first
            
            if await btn.count() > 0:
                await btn.click(force=True)
                await asyncio.sleep(0.5)
                return True
            
            return False
        except:
            return False
    
    async def execute_auto_collections(self) -> bool:
        """Execute any pending auto-collections."""
        collected_any = False
        
        # Check if brain stopped
        if self.brain and not self.brain.is_running:
            print("[BusinessWorker] Brain stopped, aborting collections")
            return False
        
        if self.should_collect():
            if await self.collect_all():
                collected_any = True
                # Always reschedule after successful collection
                if self.settings.get("business.auto_collect", False):
                    self.schedule_collect()
                    print(f"[BusinessWorker] Collection complete, next collection scheduled")
        
        return collected_any
    
    async def business_tick(self) -> bool:
        """Single tick of business logic.
        
        NOTE: This worker does NOT scrape data. Brain feeds all data via self.state.
        """
        # Execute auto-collections based on Brain's state data
        return await self.execute_auto_collections()
