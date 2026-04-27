"""BattleWorker - Executes battle-related actions."""
import asyncio
import random
from typing import Optional


class BattleWorker:
    """Stateless battle executor - follows Brain commands."""
    
    def __init__(self, browser, game_state, settings):
        self.browser = browser
        self.state = game_state
        self.settings = settings
    
    async def select_single_player_mode(self) -> bool:
        """Click single player battle mode."""
        return await self.browser.click_fast(".battle-mode-card.single")
    
    async def start_fight(self) -> bool:
        """Click start fight button on stage hub."""
        return await self.browser.click_fast(".start-fight-btn")
    
    async def proceed_from_preview(self) -> bool:
        """Click fight button on battle preview screen."""
        try:
            btn = self.browser.page.locator(".pb2-btn.pb2-fight-btn").first
            if await btn.count() > 0:
                is_enabled = await btn.evaluate("el => !el.disabled")
                if is_enabled:
                    await btn.click()
                    await asyncio.sleep(1)
                    return True
            return False
        except:
            return False
    
    async def proceed_from_boosts(self) -> bool:
        """Click fight button on pre-battle boosts screen."""
        try:
            btn = self.browser.page.locator(".b3b-fight-btn").first
            if await btn.count() > 0:
                is_enabled = await btn.evaluate("el => !el.disabled")
                if is_enabled:
                    await btn.click()
                    await asyncio.sleep(1)
                    return True
            return False
        except:
            return False
    
    async def read_skills(self) -> list:
        """Read available skill names from battle UI."""
        try:
            skill_buttons = self.browser.page.locator(
                ".b4-skill:not(.flee):not([disabled])"
            )
            
            skill_names = []
            for i in range(await skill_buttons.count()):
                btn = skill_buttons.nth(i)
                try:
                    if await btn.is_visible():
                        name_elem = btn.locator(".b4-skill-name")
                        if await name_elem.count() > 0:
                            name = await name_elem.inner_text(timeout=1000)
                            if name and name not in ["Not Equipped", "Run", "RUN", "", None]:
                                skill_names.append(name)
                except:
                    continue
            
            return skill_names
        except:
            return []
    
    async def use_skill(self) -> bool:
        """Use skill based on priority settings."""
        try:
            # Get available skills (new battle4 UI)
            skill_buttons = self.browser.page.locator(
                ".b4-skill:not(.flee):not([disabled])"
            )
            
            available_skills = []
            for i in range(await skill_buttons.count()):
                btn = skill_buttons.nth(i)
                try:
                    if await btn.is_visible():
                        name_elem = btn.locator(".b4-skill-name")
                        if await name_elem.count() > 0:
                            name = await name_elem.inner_text(timeout=1000)
                            if name and name not in ["Not Equipped", "Run", "RUN", "", None]:
                                available_skills.append((name, btn))
                except:
                    continue
            
            if not available_skills:
                return False
            
            # Try to use skill based on priority
            priority = self.settings.get("battle.skill_priority", [])
            skill_clicked = False
            
            for pref in priority:
                if pref == "none":
                    continue
                for skill_name, btn in available_skills:
                    if pref.lower() in skill_name.lower():
                        await btn.click()
                        skill_clicked = True
                        await asyncio.sleep(0.5)
                        break
                if skill_clicked:
                    break
            
            # Default to first available
            if not skill_clicked and available_skills:
                await available_skills[0][1].click()
                await asyncio.sleep(0.5)
            
            return True
        except:
            return False
    
    async def check_flee_dialog(self) -> bool:
        """Click 'No' on flee confirmation to stay and fight."""
        return await self.browser.click_fast(".preview-fight-btn, .btn-start-fight, button:has-text('Fight'), .btn-flee-no")
    
    async def proceed_from_victory(self) -> bool:
        """Click next button on victory screen."""
        return await self.browser.click_fast(".b3-post-btn.b3-post-btn-next")
    
    async def proceed_from_rewards(self) -> bool:
        """Click continue button on rewards screen."""
        return await self.browser.click_fast(".b3-post-btn")
    
    async def is_in_battle(self) -> bool:
        """Check if currently in active battle."""
        try:
            # New battle4 UI uses b4-hotbar-overlay
            panel = self.browser.page.locator(".b4-hotbar-overlay")
            if await panel.count() == 0:
                return False
            
            skills = self.browser.page.locator(
                ".b4-skill:not(.flee)"
            )
            return await skills.count() > 0
        except:
            return False
    
    async def battle_tick(self, stop_check=None) -> bool:
        """Single tick of battle logic - Brain calls this repeatedly.
        
        Args:
            stop_check: Optional callable that returns True if battle should stop
        
        NOTE: This worker does NOT scrape data. Brain feeds all data via self.state.
        """
        # Check for stop before any action
        if stop_check and stop_check():
            print("[BattleWorker] Stop requested, aborting tick")
            return False
        
        # Read state from Brain (already updated by Brain before calling this)
        state = self.state.battle.state
        
        if state == "flee_confirmation":
            return await self.check_flee_dialog()
        
        if state == "mode_selection":
            return await self.select_single_player_mode()
        
        if state == "stage_hub":
            return await self.start_fight()
        
        if state == "battle_preview":
            return await self.proceed_from_preview()
        
        if state == "pre_battle_boosts":
            return await self.proceed_from_boosts()
        
        if state == "battle_arena":
            # Check for defeat
            defeat = await self.browser.count_elements(
                "text=You Died, text=Defeat, .wb4-defeat-message"
            )
            if defeat > 0:
                await asyncio.sleep(1)
                return True
            
            # Use skill if it's our turn
            return await self.use_skill()
        
        if state == "post_battle_victory":
            return await self.proceed_from_victory()
        
        if state in ["post_battle_rewards", "post_battle"]:
            return await self.proceed_from_rewards()
        
        return False
    
    async def claim_quests(self) -> int:
        """Claim all available quest rewards. Returns number of quests claimed."""
        claimed = 0
        try:
            # Find all claimable quest cards with claim buttons
            claimable_cards = self.browser.page.locator('.dq-card.claimable')
            card_count = await claimable_cards.count()
            
            if card_count > 0:
                print(f"[BattleWorker] Found {card_count} claimable quests")
                
                # Find all claim buttons within claimable cards
                claim_buttons = claimable_cards.locator('.dq-claim-button')
                btn_count = await claim_buttons.count()
                
                for i in range(btn_count):
                    try:
                        btn = claim_buttons.nth(i)
                        if await btn.is_visible():
                            print(f"[BattleWorker] Clicking claim button {i+1}/{btn_count}")
                            await btn.click(force=True)
                            await asyncio.sleep(0.5)
                            claimed += 1
                    except Exception as e:
                        print(f"[BattleWorker] Failed to click claim button {i+1}: {e}")
            
            # Fallback: try to find any visible claim buttons on the page
            if claimed == 0:
                all_claim_buttons = self.browser.page.locator('.dq-claim-button')
                all_count = await all_claim_buttons.count()
                if all_count > 0:
                    print(f"[BattleWorker] Fallback: found {all_count} claim buttons on page")
                    for i in range(all_count):
                        try:
                            btn = all_claim_buttons.nth(i)
                            if await btn.is_visible():
                                await btn.click(force=True)
                                await asyncio.sleep(0.5)
                                claimed += 1
                        except:
                            pass
                    
            if claimed > 0:
                print(f"[BattleWorker] Claimed {claimed} quest rewards")
            return claimed
        except Exception as e:
            print(f"[BattleWorker] Error claiming quests: {e}")
            return 0

    async def execute_battle_round(self) -> bool:
        """Execute a complete battle cycle.
        
        NOTE: Brain must update battle state before each tick via self.state.update_battle_state()
        """
        # Navigate to battle page if needed
        if not self.browser.is_on_page("battle4"):
            if not await self.browser.navigate("battle4"):
                return False
            await asyncio.sleep(2)
        
        # Handle the battle flow
        max_ticks = 50
        for _ in range(max_ticks):
            result = await self.battle_tick()
            
            # Check if battle is complete
            # Brain should update state before next tick
            if self.state.battle.state == "stage_hub":
                return True
            
            if not result:
                await asyncio.sleep(0.5)
        
        return False
