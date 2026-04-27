"""Brain - Central orchestrator that controls all workers."""
import asyncio
import time
from typing import Optional

from browser import BrowserController
from state import GameState
from settings import Settings
from workers import BattleWorker, ChestWorker, BusinessWorker


class Brain:
    """Central controller that makes all decisions and delegates to workers."""
    
    def __init__(self, ui_update_callback=None, command_queue=None):
        self.browser = BrowserController()
        self.state = GameState()
        self.settings = Settings()
        self.command_queue = command_queue
        
        # Workers
        self.battle_worker = BattleWorker(self.browser, self.state, self.settings)
        self.chest_worker = ChestWorker(self.browser, self.state, self.settings, brain=self)
        self.business_worker = BusinessWorker(self.browser, self.state, self.settings, brain=self)
        
        # State
        self.is_running = False
        self.is_connected = False
        self.is_paused = False  # Paused by loot window
        self.last_sync_time = 0
        self.last_full_update = 0  # For 15-minute full data refresh
        self.last_full_scan_url = None  # Track last URL that was fully scanned
        self.last_forum_refresh = time.time()  # For 1-hour auto-refresh
        self.ui_callback = ui_update_callback
        
        # Task priorities (lower = higher priority)
        self.TASK_PRIORITY = {
            "interrupts": 0,  # Popups, rewards - handle immediately
            "battle": 1,
            "chests": 2,
            "business": 3,
        }
        
        # Bonus round cooldown to prevent loops
        self.last_bonus_round_time = 0
        self.last_reward_dismissal_time = 0
        
        # Loot window integration - signal/poll pattern
        self.loot_mode = False  # When True, brain only handles loot operations
        self.loot_navigate_requested = False
        self.loot_spins_count = None  # None = not read yet, -1 = error, number = success
        self.loot_spins_error = None
        self.loot_open_requested = False  # Request to open a chest
        self.loot_stop_requested = False  # Request to stop opening
        self.loot_last_reward = None  # Last parsed reward string for loot window
        self.loot_rewards_feed = []  # List of rewards from live feed
        self.loot_read_spins_requested = False  # Request to read current spins counter
    
    async def connect(self, cdp_url: str = "http://localhost:9222") -> bool:
        """Connect to browser."""
        self.is_connected = await self.browser.connect(cdp_url)
        if self.is_connected:
            # Navigate to forum for initial data
            await self.browser.navigate("forum")
            await self._update_state()
        return self.is_connected
    
    async def disconnect(self):
        """Disconnect from browser."""
        await self.browser.disconnect()
        self.is_connected = False
        self.is_running = False
    
    async def _update_state(self):
        """Update game state from current page - lightweight on battle pages."""
        if not self.browser.page:
            return
        
        # Only do full update (materials, etc.) on forum page
        # On battle/chests/business pages, do lightweight update (energy + page state)
        current_url = self.browser.page.url
        is_forum = "forum" in current_url
        
        if is_forum:
            # Only do full material scan when URL changes or every 15 minutes
            url_changed = (self.last_full_scan_url != current_url)
            time_for_refresh = (time.time() - self.last_full_update) >= (15 * 60)
            
            if url_changed or time_for_refresh:
                # Full update - includes materials
                print(f"[Brain] Full update - URL changed: {url_changed}, time refresh: {time_for_refresh}")
                await self.state.update_from_page(self.browser.page)
                self.last_full_scan_url = current_url
                self.last_full_update = time.time()
            else:
                # Lightweight update - no materials
                await self.state.update_from_page_lightweight(self.browser.page)
        else:
            # Lightweight update - only energy + page-specific state
            await self.state._update_energy(self.browser.page)
            if "battle" in current_url or "battle3" in current_url or "battle4" in current_url:
                await self.state.update_battle_state(self.browser.page)
                # Also update battle details (kills, stage, stats) for UI display
                await self.state._update_battle_details(self.browser.page)
                # Update quests if on battle page
                await self.state.update_quests(self.browser.page)
            elif "chest" in current_url:
                await self.state.update_chests_state(self.browser.page)
            elif "business" in current_url:
                await self.state.update_business(self.browser.page)
        
        # Notify UI
        if self.ui_callback:
            self.ui_callback(self.state)
    
    async def _handle_interrupts(self) -> bool:
        """Handle priority interrupts (rewards, popups). Returns True if handled."""
        # Check for maintenance
        if self.state.is_maintenance:
            print("[Brain] Game in maintenance mode")
            await asyncio.sleep(30)
            return True
        
        # Handle energy popup
        if self.state.has_energy_popup:
            print("[Brain] Dismissing energy popup")
            await self.browser.dismiss_energy_popup()
            await asyncio.sleep(0.5)
            return True
        
        # Handle low energy popup (click "Maybe Later")
        if await self._check_and_dismiss_low_energy_popup():
            return True
        
        # Handle Easter popup
        if self.state.has_easter_popup:
            print("[Brain] Dismissing Easter popup")
            await self.browser.dismiss_easter_popup()
            await asyncio.sleep(0.5)
            return True
        
        # Handle reward screen (chests) with cooldown to prevent loops
        if self.state.has_reward_screen:
            REWARD_COOLDOWN = 5  # seconds
            if time.time() - self.last_reward_dismissal_time >= REWARD_COOLDOWN:
                print("[Brain] Dismissing reward screen")
                await self.chest_worker.dismiss_reward()
                self.last_reward_dismissal_time = time.time()
                return True
            else:
                print(f"[Brain] Reward screen on cooldown, skipping")
                return False
        
        # Handle landing page
        if await self.browser.handle_landing_page():
            print("[Brain] Handled landing page")
            return True
        
        return False
    
    async def _should_run_battle(self) -> bool:
        """Check if battle should run."""
        print(f"[Brain] _should_run_battle called - battle_enabled: {self.settings.battle_enabled}, is_connected: {self.is_connected}")
        
        if not self.settings.battle_enabled:
            print(f"[Brain] Battle check FAILED: battle_enabled is False")
            return False
        
        min_energy = self.settings.get("battle.min_energy", 5)
        print(f"[Brain] Battle check: energy_current={self.state.energy_current}, min_energy={min_energy}")
        
        if self.state.energy_current < min_energy:
            print(f"[Brain] Battle check FAILED: Energy {self.state.energy_current} < min {min_energy}")
            return False
        
        print(f"[Brain] Battle check PASSED: enabled: {self.settings.battle_enabled}, energy: {self.state.energy_current} >= {min_energy}")
        return True
    
    async def _check_and_dismiss_low_energy_popup(self) -> bool:
        """Check for and dismiss low energy popup by clicking 'Maybe Later'."""
        try:
            # Check if popup is visible
            popup_overlay = self.browser.page.locator(".low-energy-popup-overlay")
            if await popup_overlay.is_visible():
                print("[Brain] Low energy popup detected - clicking 'Maybe Later'")
                # Click Maybe Later button
                maybe_later = popup_overlay.locator(".low-energy-popup-btn.secondary")
                if await maybe_later.count() > 0:
                    await maybe_later.click()
                    print("[Brain] Clicked 'Maybe Later' on low energy popup")
                    await asyncio.sleep(0.5)
                    return True
                # Fallback: click close button
                close_btn = popup_overlay.locator(".low-energy-popup-close")
                if await close_btn.count() > 0:
                    await close_btn.click()
                    print("[Brain] Clicked close button on low energy popup")
                    await asyncio.sleep(0.5)
                    return True
        except Exception as e:
            print(f"[Brain] Low energy popup handling error: {e}")
        return False
    
    async def _should_run_chests(self) -> bool:
        """Check if chests should run (checks settings only, availability determined after navigation)."""
        print(f"[Brain] _should_run_chests: enabled={self.settings.chests_enabled}, bronze={self.state.bronze}")
        
        if not self.settings.chests_enabled:
            print("[Brain] Chests check FAILED: not enabled")
            return False
        
        min_bronze = self.settings.get("chests.min_bronze", 0)
        print(f"[Brain] Chests check: bronze={self.state.bronze} vs min={min_bronze}")
        if self.state.bronze <= min_bronze:
            print("[Brain] Chests check FAILED: not enough bronze")
            return False
        
        # Check if user has selected any chests (actual availability checked after navigation)
        selected = self.settings.get("chests.selected", {})
        has_selected = any(selected.get("Resource", [])) or any(selected.get("Armory", []))
        print(f"[Brain] Chests check: selected={selected}, has_selected={has_selected}")
        
        if not has_selected:
            print("[Brain] Chests check FAILED: no chests selected")
            return False
        
        print("[Brain] Chests check PASSED - will check availability on chests page")
        return True
    
    async def _should_run_business(self) -> bool:
        """Check if business should run."""
        print(f"[Brain] _should_run_business: business_enabled={self.settings.business_enabled}")
        
        if not self.settings.business_enabled:
            print("[Brain] Business check FAILED: business_enabled is False")
            return False
        
        should_collect = self.business_worker.should_collect()
        
        print(f"[Brain] Business check: should_collect={should_collect}")
        
        if should_collect:
            print("[Brain] Business check PASSED")
            return True
        else:
            print("[Brain] Business check: nothing ready to collect")
            return False
    
    async def _execute_battle(self) -> bool:
        """Execute battle task - Brain updates battle state, worker executes actions."""
        print("[Brain] Executing battle task")
        
        # Ensure on battle page
        if not self.browser.is_on_page("battle4"):
            if not await self.browser.navigate("battle4"):
                return False
            await asyncio.sleep(2)
        
        # Skill validation - read and validate skills on first battle
        skills_validated = self.settings.get("battle.skills_validated", False)
        if not skills_validated:
            print("[Brain] Validating skills...")
            current_skills = await self.battle_worker.read_skills()
            saved_priority = self.settings.get("battle.skill_priority", [])
            last_skill_names = self.settings.get("battle.last_skill_names", [])
            
            # Compare current skills with last saved
            # If both are empty, they match (no skills detected yet)
            if not current_skills and not last_skill_names:
                skills_match = True
            else:
                skills_match = set(current_skills) == set(last_skill_names) if current_skills and last_skill_names else False
            
            if not skills_match:
                print(f"[Brain] Skills changed - resetting to default. Current: {current_skills}, Last: {last_skill_names}")
                # Reset to default with Attack first
                new_priority = ["Attack", "none", "none", "none", "none", "none"]
                self.settings.set("battle.skill_priority", new_priority)
                self.settings.set("battle.last_skill_names", current_skills)
                self.settings.set("battle.skills_validated", True)
                print(f"[Brain] Skills reset and saved: {new_priority}")
                # Notify UI of skill reset
                if self.ui_callback:
                    self.ui_callback({"skill_reset": True, "new_priority": new_priority})
            else:
                print("[Brain] Skills match saved settings - marking as validated")
                self.settings.set("battle.skills_validated", True)
        
        # Update battle info for UI display
        await self.state._update_energy(self.browser.page)
        await self.state.update_battle_state(self.browser.page)
        await self.state._update_battle_details(self.browser.page)
        await self.state.update_quests(self.browser.page)
        
        # Notify UI of updated battle info
        if self.ui_callback:
            self.ui_callback(self.state)
        
        battle_loop_count = 0
        
        # Brain updates battle state before worker executes
        max_ticks = 30  # Reduced from 50
        battle_started = False  # Track if we actually entered a battle
        
        for tick in range(max_ticks):
            # Check if bot was stopped
            if not self.is_running:
                print("[Brain] Battle stopping (user clicked STOP)")
                return False
            
            # Update battle state (lightweight - just detects page state)
            await self.state.update_battle_state(self.browser.page)
            
            # Track that battle actually started (not just at hub)
            if self.state.battle.state not in ["stage_hub", "unknown", None]:
                battle_started = True
            
            # Feed data to worker and execute
            result = await self.battle_worker.battle_tick(stop_check=lambda: not self.is_running)
            
            # Check if battle complete - only exit if we actually fought
            if battle_started and self.state.battle.state == "stage_hub":
                print("[Brain] Battle complete - back to stage hub")
                # Update quests after battle and claim if auto-claim enabled
                await self.state.update_quests(self.browser.page)
                if self.settings.get("auto_claim_quests", False):
                    await self.battle_worker.claim_quests()
                return True
            
            if not result:
                await asyncio.sleep(0.3)  # Reduced from 0.5
        
        print("[Brain] Battle max ticks reached")
        return False
    
    async def _execute_chests(self) -> bool:
        """Execute chests task - Brain updates chest state, worker executes actions."""
        print("[Brain] Executing chests task")
        
        # Ensure on chests page
        if not self.browser.is_on_page("chests"):
            if not await self.browser.navigate("chests"):
                return False
            await asyncio.sleep(2)  # Increased wait for page to load
        
        # NEW: Update full state after navigation (includes chests + top bar data)
        await self.state.update_from_page(self.browser.page)
        
        # Wait a bit more for chest cards to render
        await asyncio.sleep(1)
        
        # Refresh chest state specifically to ensure cards are detected
        await self.state.update_chests_state(self.browser.page)
        
        # Worker opens chests (state already updated above)
        return await self.chest_worker.execute_chest_round()
    
    async def _execute_business(self) -> bool:
        """Execute business task - Brain updates business state, worker executes actions."""
        print("[Brain] Executing business task")
        
        # Brain updates business state first
        if not self.browser.is_on_page("businesses"):
            if not await self.browser.navigate("businesses"):
                return False
            await asyncio.sleep(1)
        
        # NEW: Update full state after navigation (includes business + top bar data)
        await self.state.update_from_page(self.browser.page)
        
        # Worker executes based on Brain's state data
        return await self.business_worker.business_tick()
    
    async def tick(self) -> bool:
        """Single brain tick - returns True if any action was taken."""
        # Check if paused by loot window
        if self.is_paused:
            print("[Brain] Tick skipped - bot is paused by loot window")
            await asyncio.sleep(1)
            return False
        
        print(f"[Brain] Tick START - connected: {self.is_connected}, page: {self.browser.page is not None}")
        
        if not self.is_connected or not self.browser.page:
            print(f"[Brain] Tick skipped - connected: {self.is_connected}, page: {self.browser.page is not None}")
            return False
        
        # If in loot mode, only handle loot requests
        if self.loot_mode:
            # Handle navigation request
            nav_handled = await self._handle_loot_request()
            if nav_handled:
                return True
            
            # Handle open request
            open_handled = await self._handle_loot_open()
            if open_handled:
                return True
            
            # Handle spins counter read request
            if self.loot_read_spins_requested:
                self.loot_read_spins_requested = False
                await self._read_loot_spins_counter()
            
            # No loot requests, just wait
            await asyncio.sleep(0.5)
            return False
        
        # Update state
        await self._update_state()
        
        # Handle interrupts first
        interrupt_handled = await self._handle_interrupts()
        if interrupt_handled:
            return True
        
        # Auto-sync if enabled
        sync_interval = self.settings.get("general.sync_interval_sec", 30)
        if self.settings.get("general.auto_sync", False):
            if time.time() - self.last_sync_time >= sync_interval:
                if self.browser.is_on_page("forum"):
                    await self._update_state()
                    self.last_sync_time = time.time()
        
        # 15-minute full data refresh (only on forum page, doesn't interrupt battles)
        FULL_REFRESH_MINUTES = 15
        if time.time() - self.last_full_update >= (FULL_REFRESH_MINUTES * 60):
            if self.browser.is_on_page("forum"):
                print(f"[Brain] 15-minute full refresh - updating all data...")
                await self._update_state()
                self.last_full_update = time.time()
                print(f"[Brain] Full refresh complete")
        
        # 1-hour auto-refresh: go back to forum and refresh data (prevents stuck states)
        if self.settings.get("general.auto_refresh_1h", True):
            ONE_HOUR = 60 * 60  # 1 hour in seconds
            if time.time() - self.last_forum_refresh >= ONE_HOUR:
                print(f"[Brain] 1-hour auto-refresh triggered - returning to forum...")
                try:
                    await self.browser.navigate("forum")
                    await self._update_state()
                    self.last_forum_refresh = time.time()
                    print(f"[Brain] 1-hour refresh complete - back at forum")
                    return True  # Action taken
                except Exception as e:
                    print(f"[Brain] 1-hour refresh failed: {e}")
        
        # Update UI with business countdowns every tick (for timer display)
        self._update_business_countdowns()
        
        # Build sequence dynamically based on enabled flags
        sequence = []
        if self.settings.battle_enabled:
            sequence.append("battle")
        if self.settings.chests_enabled:
            sequence.append("chests")
        if self.settings.business_enabled:
            sequence.append("business")
        
        # Execute tasks in sequence - continue to next task even if current fails
        action_taken = False
        for task in sequence:
            if task == "battle" and await self._should_run_battle():
                result = await self._execute_battle()
                if result:
                    action_taken = True
            elif task == "chests" and await self._should_run_chests():
                result = await self._execute_chests()
                if result:
                    action_taken = True
            elif task == "business" and await self._should_run_business():
                result = await self._execute_business()
                if result:
                    action_taken = True
        
        return action_taken
    
    async def run(self):
        """Main brain loop."""
        self.is_running = True
        print("[Brain] Starting main loop")
        
        while self.is_running:
            try:
                action_taken = await self.tick()
                
                # Sleep between ticks
                if action_taken:
                    await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                print(f"[Brain] Loop error: {e}")
                await asyncio.sleep(5)
        
        print("[Brain] Main loop stopped")
    
    def stop(self):
        """Stop the brain loop."""
        self.is_running = False
    
    def pause(self):
        """Pause the brain (called by loot window)."""
        self.is_paused = True
        print("[Brain] Paused by loot window")
    
    def resume(self):
        """Resume the brain (called when loot window closes)."""
        self.is_paused = False
        print("[Brain] Resumed from loot window")
    
    # Loot window methods
    def request_loot_navigation(self):
        """Called by loot window to request navigation to battle page."""
        self.loot_navigate_requested = True
        self.loot_spins_count = None  # Reset
        self.loot_spins_error = None
        print("[Brain] Loot navigation requested")
    
    def request_loot_open(self):
        """Called by loot window to request opening a chest."""
        self.loot_open_requested = True
        print("[Brain] Loot open requested")
    
    def request_loot_stop(self):
        """Called by loot window to stop opening chests."""
        self.loot_stop_requested = True
        print("[Brain] Loot stop requested")
    
    async def _handle_loot_request(self) -> bool:
        """Handle loot window navigation request. Returns True if handled."""
        if not self.loot_navigate_requested:
            return False
        
        self.loot_navigate_requested = False
        
        try:
            print("[Brain] Handling loot navigation request")
            
            # Navigate to battle page
            if not await self.browser.navigate("https://game.tokenlordsrpg.com/battle4"):
                self.loot_spins_count = -1
                self.loot_spins_error = "Navigation failed"
                return True
            
            await asyncio.sleep(2)
            
            # Wait for spins element
            try:
                spins_elem = self.browser.page.locator(".b3-co-spins-num")
                await spins_elem.wait_for(state="visible", timeout=10000)
                
                spins_text = await spins_elem.inner_text()
                self.loot_spins_count = int(spins_text.replace(",", ""))
                print(f"[Brain] Loot spins read: {self.loot_spins_count}")
            except Exception as e:
                self.loot_spins_count = -1
                self.loot_spins_error = str(e)
                print(f"[Brain] Loot spins read error: {e}")
            
            return True
            
        except Exception as e:
            self.loot_spins_count = -1
            self.loot_spins_error = str(e)
            print(f"[Brain] Loot navigation error: {e}")
            return True
    
    async def _handle_loot_open(self) -> bool:
        """Handle loot window chest opening request. Returns True if handled."""
        if not self.loot_open_requested:
            return False
        
        self.loot_open_requested = False
        self.loot_last_reward = None  # Reset
        
        try:
            print("[Brain] Handling loot open request")
            
            # Try to open chest
            open_btn = self.browser.page.locator(".b4c-chest-cta")
            if await open_btn.is_visible():
                await open_btn.click(force=True)
                await asyncio.sleep(2)
                
                # Parse reward from result div
                await self._parse_loot_reward()
                
                # Dismiss reward if present
                reward_btn = self.browser.page.locator(".slot-chest-reward-dismiss")
                if await reward_btn.is_visible():
                    await reward_btn.click(force=True)
                    await asyncio.sleep(1)
                
                # Try bonus spins
                bonus_btn = self.browser.page.locator(".slot-open-bonus")
                if await bonus_btn.is_visible():
                    await bonus_btn.click(force=True)
                    await asyncio.sleep(1)
                    
                    # Click awesome button after bonus
                    awesome_btn = self.browser.page.locator(".awesome-button")
                    if await awesome_btn.is_visible():
                        await awesome_btn.click(force=True)
                        await asyncio.sleep(1)
                
                return True
            else:
                # Try open again button
                open_again = self.browser.page.locator(".b4c-open-again")
                if await open_again.is_visible():
                    await open_again.click(force=True)
                    await asyncio.sleep(2)
                    return True
                
                print("[Brain] No open button visible")
                return False
                
        except Exception as e:
            print(f"[Brain] Loot open error: {e}")
            return False
    
    async def _parse_loot_reward(self):
        """Parse rewards from battle page live feed."""
        try:
            feed_list = self.browser.page.locator(".wbs-live-feed-list")
            if await feed_list.is_visible():
                items = feed_list.locator(".wbs-live-item")
                rewards = []
                
                for i in range(await items.count()):
                    item = items.nth(i)
                    player = await item.locator(".wbs-live-player").inner_text()
                    reward = await item.locator(".wbs-live-reward").inner_text()
                    tier = await item.locator(".wbs-live-tier").inner_text()
                    amount = await item.locator(".wbs-live-amount").inner_text()
                    
                    rewards.append({
                        "player": player.strip(),
                        "reward": reward.strip(),
                        "tier": tier.strip(),
                        "amount": amount.strip()
                    })
                
                self.loot_rewards_feed = rewards
                print(f"[Brain] Parsed {len(rewards)} rewards from live feed")
        except Exception as e:
            print(f"[Brain] Live feed parse error: {e}")
            self.loot_rewards_feed = []
    
    async def _read_loot_spins_counter(self) -> bool:
        """Read current spins counter from battle page."""
        try:
            counter_elem = self.browser.page.locator(".b4c-counter-value")
            if await counter_elem.is_visible():
                spins_text = await counter_elem.inner_text()
                self.loot_spins_count = int(spins_text.replace(",", ""))
                return True
            return False
        except Exception as e:
            print(f"[Brain] Spins counter read error: {e}")
            return False
    
    # User command handlers
    def _update_business_countdowns(self):
        """Update UI with business countdown information."""
        if not self.ui_callback:
            return
        
        # Get countdown info from business worker
        collect_countdown = self.business_worker.get_collect_countdown()
        
        # Update UI via callback
        self.ui_callback({
            "collect_countdown": collect_countdown,
            "auto_collect": self.settings.get("business.auto_collect", False)
        })
    
    def set_battle_enabled(self, enabled: bool):
        """Enable/disable battle automation."""
        self.settings.battle_enabled = enabled
        print(f"[Brain] Battle automation: {enabled}")
    
    def set_chests_enabled(self, enabled: bool):
        """Enable/disable chests automation."""
        self.settings.chests_enabled = enabled
        print(f"[Brain] Chests automation: {enabled}")
    
    def set_business_enabled(self, enabled: bool):
        """Enable/disable business automation."""
        self.settings.business_enabled = enabled
        print(f"[Brain] Business automation: {enabled}")
    
    def set_business_auto_collect(self, enabled: bool):
        """Enable/disable auto Collect All."""
        self.settings.set("business.auto_collect", enabled)
        print(f"[Brain] Auto Collect All: {enabled}")
        # Don't schedule immediately - let the first tick handle immediate collection
        # when next_collect_at is 0, then schedule after collection
    
    def set_business_collect_interval(self, minutes: int):
        """Set temporary Collect All interval for this session only (not saved)."""
        # Validate input
        try:
            minutes = int(minutes)
            if minutes < 1:
                minutes = 1
            # Store in worker as custom interval (not saved to settings)
            self.business_worker.custom_collect_interval = minutes
            print(f"[Brain] Collect All interval set to {minutes} minutes (temporary)")
            # Only reschedule if timer was already set (not 0), to allow immediate collection on first enable
            if self.settings.get("business.auto_collect", False) and self.business_worker.next_collect_at > 0:
                self.business_worker.schedule_collect()
        except (ValueError, TypeError):
            pass  # Invalid input, ignore
    
    def get_status(self) -> dict:
        """Get current status for UI display."""
        return {
            "connected": self.is_connected,
            "running": self.is_running,
            "player": {
                "name": self.state.player_name,
                "class": self.state.player_class,
                "level": self.state.level,
                "xp": f"{self.state.xp_current:,} / {self.state.xp_max:,}",
                "xp_progress": self.state.xp_progress,
                "skill_points": self.state.player_stats.skill_points,
                "gear_tier": self.state.player_stats.gear_tier,
                "total_attack": self.state.player_stats.total_attack,
                "total_defense": self.state.player_stats.total_defense,
                "total_hp": self.state.player_stats.total_hp,
                "hp_current": self.state.player_stats.hp_current,
                "hp_max": self.state.player_stats.hp_max,
                "weekly_energy_current": self.state.weekly_energy_current,
                "weekly_energy_required": self.state.weekly_energy_required,
                "weekly_energy_progress": self.state.weekly_energy_progress,
            },
            "energy": {
                "current": self.state.energy_current,
                "max": self.state.energy_max,
                "progress": self.state.energy_progress,
                "timer": self.state.energy_timer,
            },
            "currency": {
                "bronze": self.state.bronze,
                "tlrpg": self.state.tlrpg,
                "tlrpg_eur": self.state.tlrpg_eur,
                "balance": self.state.balance,
            },
            "materials": self.state.materials,
            "battle": {
                "enabled": self.settings.battle_enabled,
                "stage": self.state.battle.current_stage,
                "kills": self.state.battle.kills,
                "state": self.state.battle.state,
                "attack": self.state.battle.attack,
                "defense": self.state.battle.defense,
                "streak": self.state.battle.current_streak,
                "bounty_target": self.state.battle.bounty_target,
                "bounty_reward": self.state.battle.bounty_reward,
                "skill_priority": self.settings.get("battle.skill_priority", []),
            },
            "chests": {
                "enabled": self.settings.chests_enabled,
                "bronze": self.state.current_bronze,
                "available_chests": [
                    {
                        "name": c.name,
                        "category": c.category,
                        "cost": c.bronze_cost,
                        "cooldown": c.cooldown_time,
                        "can_summon": c.can_summon,
                    }
                    for c in self.state.chests
                ],
            },
            "quests": [
                {
                    "name": q.name,
                    "progress_pct": q.progress_pct,
                    "status": q.status,
                    "reward": q.reward,
                    "description": q.description,
                    "can_claim": q.can_claim,
                }
                for q in self.state.daily_quests
            ],
            "business": {
                "enabled": self.settings.business_enabled,
                "stored_bronze": self.state.business.stored_bronze,
                "bronze_progress": self.state.business.bronze_progress,
                "bronze_capacity": self.state.business.bronze_capacity,
                "stored_materials": self.state.business.stored_materials,
                "materials_ready": self.state.business.materials_ready,
                "collection_ready": self.state.business.collection_ready,
                "next_collection_time": self.state.business.next_collection_time,
                "collect_countdown": self.business_worker.get_collect_countdown(),
            },
        }
