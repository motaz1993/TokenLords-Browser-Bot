"""ChestWorker - Executes chest-related actions."""
import asyncio


class ChestWorker:
    """Stateless chest executor - follows Brain commands."""
    
    CHEST_TYPES = {
        "Resource": ["Wood Chest", "Bronze Chest", "Silver Chest", "Gold Chest", 
                     "Diamond Chest", "Ruby Chest", "Emerald Chest"],
        "Armory": ["Wood Armory", "Bronze Armory", "Silver Armory", "Gold Armory",
                   "Diamond Armory", "Ruby Armory", "Emerald Armory"]
    }
    
    def __init__(self, browser, game_state, settings, brain=None):
        self.browser = browser
        self.state = game_state
        self.settings = settings
        self.brain = brain
    
    async def switch_tab(self, category: str) -> bool:
        """Switch between Resource and Armory tabs."""
        try:
            tab_btn = self.browser.page.locator(f".sc-tab:has-text('{category}')")
            if await tab_btn.count() == 0:
                return False
            
            # Check if already active
            is_active = await tab_btn.evaluate("node => node.classList.contains('active')")
            if is_active:
                return True
            
            await tab_btn.click(force=True)
            
            # Wait for tab content
            search_term = "Armory" if category == "Armory" else "Chest"
            try:
                await self.browser.page.wait_for_selector(
                    f".sc-chest-card:has-text('{search_term}')", 
                    timeout=2000
                )
            except:
                await asyncio.sleep(1)
            
            return True
        except:
            return False
    
    async def dismiss_reward(self) -> bool:
        """Dismiss reward screen."""
        try:
            btn = self.browser.page.locator(".slot-chest-reward-dismiss")
            if await btn.is_visible():
                await btn.click(force=True)
                await asyncio.sleep(0.8)
                return True
            return False
        except:
            return False
    
    async def handle_bonus_round(self) -> bool:
        """Handle bonus round by clicking the bonus button until it disappears."""
        try:
            bonus_btn = self.browser.page.locator(".slot-open-bonus")
            bonus_counter = self.browser.page.locator(".ps-bonus-counter, .ps-bonus-counter-value").first
            
            # Debug: Check if bonus counter exists
            counter_count = await bonus_counter.count()
            if counter_count > 0:
                counter_text = await bonus_counter.inner_text()
                print(f"[ChestWorker] Bonus counter found: {counter_text}")
            
            # Wait for bonus button to appear (poll for element existence, not visibility)
            import time
            start_time = time.time()
            button_found = False
            while time.time() - start_time < 3:  # 3 second timeout
                if await bonus_btn.count() > 0:
                    button_found = True
                    print("[ChestWorker] Bonus button found in DOM")
                    break
                await asyncio.sleep(0.2)  # Poll every 200ms
            
            if not button_found:
                url = self.browser.page.url
                print(f"[ChestWorker] No bonus button found (timeout) - URL: {url}")
                return False
            
            # Debug: Check initial state
            bonus_count = await bonus_btn.count()
            print(f"[ChestWorker] Bonus button count: {bonus_count}")
            is_visible = await bonus_btn.is_visible()
            print(f"[ChestWorker] Bonus button visible: {is_visible}")
            if is_visible:
                button_text = await bonus_btn.inner_text()
                print(f"[ChestWorker] Bonus button text: {button_text}")
            
            max_spins = 20  # Safety limit
            spins_done = 0
            
            while spins_done < max_spins:
                # Check if bonus button is still visible
                if not await bonus_btn.is_visible():
                    print("[ChestWorker] Bonus button no longer visible - round complete")
                    # Click Awesome button to close modal
                    await self.click_awesome_button()
                    return True
                
                # Click bonus spin button
                print(f"[ChestWorker] Clicking bonus spin {spins_done + 1}")
                try:
                    await bonus_btn.click(force=True)
                except Exception as click_error:
                    print(f"[ChestWorker] Click error: {click_error}")
                    # Try to re-locate the button
                    bonus_btn = self.browser.page.locator(".slot-open-bonus")
                    if await bonus_btn.count() == 0:
                        print("[ChestWorker] Button disappeared after click error")
                        await self.click_awesome_button()
                        return True
                    await bonus_btn.click(force=True)
                
                await asyncio.sleep(1.0)  # Faster delay between spins
                spins_done += 1
            
            # Click Awesome button to close modal after max spins
            await self.click_awesome_button()
            return True
        except Exception as e:
            print(f"[ChestWorker] Bonus spin error: {e}")
            # Try to click Awesome button even on error
            await self.click_awesome_button()
            return False
    
    async def click_awesome_button(self) -> bool:
        """Click the Awesome button to close bonus complete modal."""
        try:
            awesome_btn = self.browser.page.locator(".ps-bonus-complete-btn")
            # Wait a bit for modal to appear
            await asyncio.sleep(0.5)
            if await awesome_btn.count() > 0 and await awesome_btn.is_visible():
                print("[ChestWorker] Clicking Awesome button")
                await awesome_btn.click(force=True)
                await asyncio.sleep(0.5)
                return True
            return False
        except Exception as e:
            print(f"[ChestWorker] Awesome button error: {e}")
            return False
    
    async def summon_chest(self, chest_name: str) -> bool:
        """Open a specific chest by name."""
        try:
            # Find the chest card
            cards = self.browser.page.locator(".sc-chest-card")
            target_card = None
            
            for i in range(await cards.count()):
                card = cards.nth(i)
                name_elem = card.locator(".chest-name, .sc-chest-name")
                if await name_elem.count() > 0:
                    name = await name_elem.inner_text()
                    if name.strip() == chest_name:
                        target_card = card
                        break
            
            if not target_card:
                return False
            
            # Click the card
            await target_card.click(force=True)
            await asyncio.sleep(3.0)  # Increased wait for summon button to appear
            
            # Click summon button with retry logic
            summon_btn = self.browser.page.locator(".slot-open-bronze, button:has-text('Open')").first
            
            # Try up to 3 times to find and click the summon button
            for attempt in range(3):
                btn_visible = await summon_btn.is_visible()
                print(f"[ChestWorker] Summon button visible (attempt {attempt + 1}): {btn_visible}")
                
                if btn_visible:
                    await summon_btn.click(force=True)
                    print("[ChestWorker] Clicked summon button")
                    await asyncio.sleep(2.0)  # Wait for slot machine UI to load
                    
                    # Handle bonus spins for this chest
                    await self.handle_bonus_for_chest()
                    
                    return True
                else:
                    if attempt < 2:
                        await asyncio.sleep(1.0)  # Wait before retrying
            
            print("[ChestWorker] Summon button not visible after retries - may be on cooldown")
            return False
        except Exception as e:
            print(f"[ChestWorker] Summon chest error: {e}")
            return False
    
    async def handle_bonus_for_chest(self) -> bool:
        """Handle bonus spins for the current chest before proceeding."""
        try:
            # First, dismiss any reward screen that might be showing
            reward_btn = self.browser.page.locator(".slot-chest-reward-dismiss")
            if await reward_btn.is_visible():
                print("[ChestWorker] Dismissing reward screen before checking bonus")
                await reward_btn.click(force=True)
                await asyncio.sleep(0.8)
            
            bonus_btn = self.browser.page.locator(".slot-open-bonus")
            # Increased wait for bonus button to appear
            await asyncio.sleep(1.5)
            
            if await bonus_btn.is_visible():
                print("[ChestWorker] Bonus button visible - handling bonus spins")
                max_bonus_spins = 20
                spins = 0
                while spins < max_bonus_spins and await bonus_btn.is_visible():
                    await bonus_btn.click(force=True)
                    await asyncio.sleep(1.0)
                    spins += 1
                print(f"[ChestWorker] Bonus spins complete - {spins} spins")
                await self.click_awesome_button()
                return True
            else:
                print("[ChestWorker] No bonus button visible - checking for reward screen")
                # Check if there's a reward screen to dismiss
                reward_btn = self.browser.page.locator(".slot-chest-reward-dismiss")
                if await reward_btn.is_visible():
                    print("[ChestWorker] Dismissing reward screen")
                    await reward_btn.click(force=True)
                    await asyncio.sleep(0.8)
                return False
        except Exception as e:
            print(f"[ChestWorker] Bonus handling error: {e}")
            return False
    
    async def open_next_available_chest(self, category: str = None) -> bool:
        """Open the next available chest based on settings.
        
        NOTE: This worker does NOT scrape data. Brain feeds all data via self.state.
        """
        # Get selected chests from settings
        selected = self.settings.get("chests.selected", {})
        
        # Determine categories to check
        categories = [category] if category else ["Resource", "Armory"]
        
        for cat in categories:
            # Switch to tab (action, not scraping)
            if not await self.switch_tab(cat):
                continue
            
            # Read available chests from Brain's GameState (NOT scraping)
            available = self.state.get_available_chests(cat)
            
            # Filter by user selection
            cat_selected = selected.get(cat, [])
            for chest in available:
                if chest.name in cat_selected:
                    return await self.summon_chest(chest.name)
        
        return False
    
    async def chest_tick(self) -> bool:
        """Single tick of chest logic.
        
        NOTE: This worker does NOT scrape data. Brain feeds all data via self.state.
        """
        # Handle reward dismissal first
        if self.state.has_reward_screen:
            return await self.dismiss_reward()
        
        # Handle bonus round
        if self.state.has_bonus_round:
            return await self.open_bonus()
        
        # Check safety limit
        min_bronze = self.settings.get("chests.min_bronze", 0)
        if self.state.current_bronze <= min_bronze:
            return False
        
        # Try to open next chest
        return await self.open_next_available_chest()
    
    async def execute_chest_round(self) -> bool:
        """Execute chest opening cycle - opens ALL selected chests available."""
        print("[ChestWorker] Starting chest round - will open ALL available selected chests")
        
        # Navigate to chests page once
        if "chest" not in self.browser.page.url:
            print("[ChestWorker] Navigating to chests page")
            await self.browser.navigate("https://game.tokenlordsrpg.com/chests")
            await asyncio.sleep(1)
        
        # PRIORITY 1: Reward Dismissal (Clears the screen immediately)
        reward_btn = self.browser.page.locator(".slot-chest-reward-dismiss")
        if await reward_btn.is_visible():
            print("[ChestWorker] Dismissing reward screen")
            await reward_btn.click(force=True)
            await asyncio.sleep(0.8)
            return True
        
        opened_any = False
        selected = self.settings.get("chests.selected", {})
        opened_chests = set()  # Track chests already opened this round
        
        # Process both categories
        for category in ["Resource", "Armory"]:
            # Skip category if no chests are selected for it
            cat_selected = selected.get(category, [])
            if not cat_selected:
                print(f"[ChestWorker] Skipping {category} - no chests selected")
                continue
            
            print(f"[ChestWorker] Processing {category} category with {len(cat_selected)} selected chests")
            
            # Switch to category tab
            if not await self.switch_tab(category):
                print(f"[ChestWorker] Failed to switch to {category} tab")
                continue
            
            # Keep trying to open chests until no more are available or all selected are opened
            max_attempts = len(cat_selected) + 5  # Safety limit
            attempts = 0
            failed_chests = {}  # Track failed attempts per chest name
            
            while attempts < max_attempts:
                # Check if brain stopped
                if self.brain and not self.brain.is_running:
                    print("[ChestWorker] Brain stopped, aborting chest round")
                    break
                
                # Refresh chest state to check for cooldowns
                await self.state.update_chests_state(self.browser.page)
                await asyncio.sleep(0.3)
                
                # Get currently available chests for this category
                available = self.state.get_available_chests(category)
                
                # Find an unopened selected chest that's available
                chest_to_open = None
                for chest in available:
                    if chest.name in cat_selected and chest.name not in opened_chests:
                        # Skip if this chest has failed too many times (likely on cooldown)
                        if chest.name in failed_chests and failed_chests[chest.name] >= 3:
                            print(f"[ChestWorker] Skipping {chest.name} - failed {failed_chests[chest.name]} times, likely on cooldown")
                            continue
                        chest_to_open = chest
                        break
                
                if not chest_to_open:
                    print(f"[ChestWorker] No more selected chests available in {category}")
                    break
                
                # Dismiss any reward screen before opening next chest
                reward_btn = self.browser.page.locator(".slot-chest-reward-dismiss")
                if await reward_btn.is_visible():
                    print("[ChestWorker] Dismissing reward screen before opening chest")
                    await reward_btn.click(force=True)
                    await asyncio.sleep(0.8)
                
                # Open the chest
                print(f"[ChestWorker] Opening {chest_to_open.name} (cost: {chest_to_open.bronze_cost})")
                result = await self.summon_chest(chest_to_open.name)
                if result:
                    opened_any = True
                    opened_chests.add(chest_to_open.name)
                    print(f"[ChestWorker] Successfully opened {chest_to_open.name}")
                    # Reset failure counter on success
                    if chest_to_open.name in failed_chests:
                        del failed_chests[chest_to_open.name]
                else:
                    print(f"[ChestWorker] Failed to open {chest_to_open.name} - may be on cooldown")
                    # Track failure
                    failed_chests[chest_to_open.name] = failed_chests.get(chest_to_open.name, 0) + 1
                    if failed_chests[chest_to_open.name] >= 3:
                        print(f"[ChestWorker] {chest_to_open.name} failed {failed_chests[chest_to_open.name]} times, skipping for this round")
                
                # Wait for animation/page update
                await asyncio.sleep(1)
                attempts += 1
        
        print(f"[ChestWorker] Round complete. Opened any chests: {opened_any}")
        return opened_any
