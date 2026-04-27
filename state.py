"""GameState - Single source of truth for all scraped game data."""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PlayerStats:
    """Player stats and gear information."""
    skill_points: int = 0
    gear_tier: int = 0  # Average gear tier 1-10
    total_attack: int = 0
    total_defense: int = 0
    total_hp: int = 0
    hp_current: int = 0
    hp_max: int = 0


@dataclass
class BattleState:
    """Battle-related game state."""
    current_stage: str = ""
    kills: int = 0
    state: str = "unknown"  # unknown, mode_selection, stage_hub, battle_preview, pre_battle_boosts, battle_arena, post_battle_victory, post_battle_rewards, post_battle, flee_confirmation
    has_active_battle: bool = False
    available_skills: List[Tuple[str, str]] = field(default_factory=list)  # (name, selector)
    # NEW FIELDS:
    attack: int = 0
    defense: int = 0
    current_streak: int = 0
    bounty_target: str = ""  # Current bounty target name
    bounty_reward: str = ""  # Bounty reward amount


@dataclass
class ChestInfo:
    """Information about a single chest."""
    name: str = ""
    category: str = ""  # Resource or Armory
    is_locked: bool = False
    is_tlrpg_only: bool = False
    is_on_cooldown: bool = False
    can_summon: bool = False
    # NEW FIELDS:
    bronze_cost: int = 0
    cooldown_time: str = ""  # "2h 30m" or "Ready"


@dataclass
class BusinessState:
    """Business-related game state."""
    stored_bronze: int = 0
    bronze_capacity: int = 0
    bronze_progress: float = 0.0
    stored_materials: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # name -> (current, max)
    material_progress: Dict[str, float] = field(default_factory=dict)
    # NEW FIELDS:
    materials_ready: List[str] = field(default_factory=list)  # Which can be collected
    collection_ready: bool = False  # Quick check if anything ready
    next_collection_time: str = ""  # Time until next material ready


@dataclass
class Quest:
    """Daily quest information."""
    name: str = ""
    progress_pct: int = 0  # 0-100
    status: str = ""  # "in_progress", "completed", "claimable"
    reward: str = ""  # e.g., "460 🪙 +2 🎰"
    description: str = ""  # e.g., "63 / 250 kills"
    can_claim: bool = False
    button_selector: str = ""  # Selector for claim button if available


class GameState:
    """Central game state - scraped from browser and shared across components."""
    
    # Material names for reference
    MATERIAL_NAMES = ["Wood", "Wheat", "Rock", "Food", "Cloth"]
    RARE_MATERIALS = ["Ember", "Verdite", "Moonite", "Stormis", "Drakon", 
                      "Voidium", "Celest", "Mythril", "Eternium", "Chronis"]
    
    def __init__(self):
        # Player info
        self.player_name: str = ""
        self.player_class: str = ""
        self.level: int = 0
        self.xp_current: int = 0
        self.xp_max: int = 0
        self.xp_progress: float = 0.0
        
        # Energy
        self.energy_current: float = 0.0
        self.energy_max: float = 0.0
        self.energy_progress: float = 0.0
        self.energy_timer: str = ""
        
        # Currency
        self.bronze: int = 0
        self.tlrpg: float = 0.0
        self.tlrpg_eur: str = ""
        self.balance: str = ""
        
        # Materials
        self.materials: Dict[str, str] = {}
        
        # Battle state
        self.battle = BattleState()
        
        # Player stats
        self.player_stats = PlayerStats()
        
        # Chests
        self.chests: List[ChestInfo] = []
        self.current_bronze: int = 0  # From chests page
        
        # Quests
        self.daily_quests: List[Quest] = []
        
        # Business
        self.business = BusinessState()
        self.business_stored: Dict[str, int] = {}  # Stored materials/bronze in business
        
        # Screen states
        self.has_reward_screen: bool = False
        self.has_bonus_round: bool = False
        self.has_energy_popup: bool = False
        self.has_easter_popup: bool = False
        self.is_maintenance: bool = False
        
        # Current URL
        self.current_url: str = ""
        
        # Weekly payout requirements
        self.weekly_energy_current: int = 0
        self.weekly_energy_required: int = 0
        self.weekly_energy_progress: float = 0.0
    
    async def update_from_page(self, page) -> None:
        """Update all state from current page - routes based on URL."""
        if not page:
            return
        
        self.current_url = page.url
        print(f"[GameState] update_from_page START - URL: {self.current_url}")
        
        # Always update top-bar data (available on any page)
        print("[GameState] Calling _update_player_info...")
        await self._update_player_info(page)
        print("[GameState] _update_player_info completed")
        
        print("[GameState] Calling _update_energy...")
        await self._update_energy(page)
        print("[GameState] _update_energy completed")
        
        print("[GameState] Calling _update_currency...")
        await self._update_currency(page)
        print("[GameState] _update_currency completed")
        
        print("[GameState] Calling _update_materials...")
        await self._update_materials(page)
        print("[GameState] _update_materials completed")
        
        print("[GameState] Calling _update_screen_states...")
        await self._update_screen_states(page)
        print("[GameState] _update_screen_states completed")
        
        # Route page-specific updates based on URL
        url = page.url.lower()
        if "battle3" in url or "/battle4" in url or "/battle" in url:
            print("[GameState] Calling update_battle_state...")
            await self.update_battle_state(page)
            print("[GameState] update_battle_state completed")
            print("[GameState] Calling _update_battle_details...")
            await self._update_battle_details(page)
            print("[GameState] _update_battle_details completed")
            print("[GameState] Calling update_quests...")
            await self.update_quests(page)
            print("[GameState] update_quests completed")
        elif "chests" in url or "/chest" in url:
            print("[GameState] Calling update_chests...")
            await self.update_chests(page)
            print("[GameState] update_chests completed")
        elif "business" in url or "/business" in url:
            print("[GameState] Calling update_business...")
            await self.update_business(page)
            print("[GameState] update_business completed")
        
        print("[GameState] update_from_page COMPLETED")
    
    async def update_from_page_lightweight(self, page):
        """Lightweight update - only top bar data (no materials)."""
        await self._update_player_info(page)
        await self._update_energy(page)
        await self._update_currency(page)
    
    async def _update_player_info(self, page):
        """Update player name, level, xp, class, and weekly payout requirements."""
        try:
            print("[GameState] _update_player_info START")
            # Use actual selectors from the game
            name_elem = page.locator(".th-sidebar-player__name").first
            if await name_elem.count() > 0:
                self.player_name = await name_elem.inner_text()
                print(f"[GameState] Player name: {self.player_name}")
            else:
                print("[GameState] Player name not found (selectors)")
                # Try JavaScript fallback
                try:
                    player_info = await page.evaluate(r'''() => {
                        const result = {};
                        const nameEl = document.querySelector('.th-sidebar-player__name');
                        if (nameEl) {
                            result.name = nameEl.textContent.trim();
                        }
                        return result;
                    }''')
                    if 'name' in player_info and player_info['name']:
                        self.player_name = player_info['name']
                        print(f"[GameState] Player name (JS): {self.player_name}")
                    else:
                        print("[GameState] Player name not found (JS)")
                except:
                    print("[GameState] Player name not found (JS error)")
            
            # Get level from actual selector
            level_elem = page.locator(".th-sidebar-player__level").first
            if await level_elem.count() > 0:
                level_text = await level_elem.inner_text()
                level_match = re.search(r'Level\s*(\d+)', level_text, re.IGNORECASE)
                if level_match:
                    self.level = int(level_match.group(1))
                    print(f"[GameState] Player level: {self.level}")
            else:
                print("[GameState] Player level not found (selectors)")
                # Try JavaScript fallback
                try:
                    level_info = await page.evaluate(r'''() => {
                        const result = {};
                        const levelEl = document.querySelector('.th-sidebar-player__level');
                        if (levelEl) {
                            const text = levelEl.textContent.trim();
                            const match = text.match(/Level\s*(\d+)/i);
                            if (match) result.level = parseInt(match[1]);
                        }
                        return result;
                    }''')
                    if 'level' in level_info and level_info['level']:
                        self.level = level_info['level']
                        print(f"[GameState] Player level (JS): {self.level}")
                except:
                    pass
            
            # Get XP from new top-xp-text (format: "41.0K/67.8K")
            xp_elem = page.locator(".top-xp-text").first
            if await xp_elem.count() > 0:
                xp_text = await xp_elem.inner_text()
                self._parse_xp(xp_text)
                print(f"[GameState] Player XP: {self.xp_current}/{self.xp_max}")
            else:
                # Fallback to xp bar title attribute
                xp_bar = page.locator(".top-xp-bar-wide").first
                if await xp_bar.count() > 0:
                    title = await xp_bar.get_attribute("title") or ""
                    self._parse_xp(title.replace(" XP", ""))
                    print(f"[GameState] Player XP (fallback): {self.xp_current}/{self.xp_max}")
                else:
                    print("[GameState] Player XP not found (selectors)")
                    # Try JavaScript fallback
                    try:
                        xp_info = await page.evaluate(r'''() => {
                            const result = {};
                            const xpEl = document.querySelector('.top-xp-text') ||
                                         document.querySelector('[class*="xp-text"]') ||
                                         document.querySelector('[class*="xp"]');
                            if (xpEl) result.xp = xpEl.textContent.trim();
                            return result;
                        }''')
                        if 'xp' in xp_info and xp_info['xp']:
                            self._parse_xp(xp_info['xp'])
                            print(f"[GameState] Player XP (JS): {self.xp_current}/{self.xp_max}")
                    except:
                        pass
            
            # Get class from avatar image URL (e.g., /classpictures/Warrior.webp)
            # Still using fm-profile-bar-avatar as mentioned by user
            avatar_elem = page.locator(".fm-profile-bar-avatar, .b3-hero-img, img[class*='avatar']").first
            if await avatar_elem.count() > 0:
                src = await avatar_elem.get_attribute("src") or ""
                class_match = re.search(r'/classpictures/(\w+)\.', src, re.IGNORECASE)
                if class_match:
                    self.player_class = class_match.group(1)
            
            # Also check b3-hero-class for class name
            class_elem = page.locator(".b3-hero-class").first
            if await class_elem.count() > 0:
                class_text = await class_elem.inner_text()
                if class_text:
                    self.player_class = class_text.strip()
            
            # Get weekly payout requirements from new fm-card structure
            weekly_label = page.locator(".fm-req-energy-label").first
            if await weekly_label.count() > 0:
                label_text = await weekly_label.inner_text()
                # Parse " Energy Used 90 / 350" format
                match = re.search(r'(\d+)\s*/\s*(\d+)', label_text)
                if match:
                    self.weekly_energy_current = int(match.group(1))
                    self.weekly_energy_required = int(match.group(2))
                    if self.weekly_energy_required > 0:
                        self.weekly_energy_progress = self.weekly_energy_current / self.weekly_energy_required
            
            # Get gear tier from battle panel
            gear_elem = page.locator(".b3-gear-tier-badge").first
            if await gear_elem.count() > 0:
                gear_text = await gear_elem.inner_text()
                tier_match = re.search(r'(\d+)', gear_text)
                if tier_match:
                    self.player_stats.gear_tier = int(tier_match.group(1))
                    
        except Exception as e:
            print(f"[GameState] Player info update error: {e}")
        
        # Parse XP
        try:
            xp_elem = page.locator(".top-xp-text").first
            if await xp_elem.count() > 0:
                xp_text = await xp_elem.inner_text()
                xp_text = await xp_elem.inner_text(timeout=2000)
                print(f"[GameState] Parsing XP: {xp_text}")
                self._parse_xp(xp_text)
        except Exception as e:
            print(f"[GameState] XP parse error: {e}")
        
        # Parse Weekly Payout Requirements
        await self._update_weekly_payout(page)
    
    async def _update_weekly_payout(self, page):
        """Parse weekly payout requirements from forum page."""
        try:
            # Energy used: "77 / 350"
            energy_elem = page.locator(".fm-req-energy-label span:last-child").first
            if await energy_elem.count() > 0:
                energy_text = await energy_elem.inner_text(timeout=2000)
                print(f"[GameState] Weekly energy text: {energy_text}")
                if '/' in energy_text:
                    parts = energy_text.split('/')
                    if len(parts) == 2:
                        current = float(parts[0].strip())
                        required = float(parts[1].strip())
                        self.weekly_energy_current = current
                        self.weekly_energy_required = required
                        self.weekly_energy_progress = current / required if required > 0 else 0
                        print(f"[GameState] Weekly energy: {current}/{required} ({self.weekly_energy_progress:.1%})")
        except Exception as e:
            print(f"[GameState] Weekly payout parse error: {e}")
    
    def _parse_xp(self, xp_text: str):
        """Parse XP text like '1234 / 5678', '7.9K / 10K', or '67.8XP'."""
        try:
            # Remove common prefixes/suffixes
            xp_clean = xp_text.replace("XP:", "").replace("XP", "").replace(" ", "").strip()
            if '/' in xp_clean:
                cur_str, tot_str = xp_clean.split('/')
                self.xp_current = self._parse_number(cur_str)
                self.xp_max = self._parse_number(tot_str)
            else:
                # Single value like "67.8XP" - treat as current XP
                self.xp_current = self._parse_number(xp_clean)
                self.xp_max = 0
            if self.xp_max > 0:
                self.xp_progress = min(1.0, self.xp_current / self.xp_max)
            print(f"[GameState] XP parsed: {self.xp_current}/{self.xp_max}")
        except Exception as e:
            print(f"[GameState] XP parse error: {e}")
    
    def _parse_number(self, val_str: str) -> int:
        """Parse number with K suffix."""
        val_str = val_str.strip().upper()
        if 'K' in val_str:
            return int(float(val_str.replace('K', '')) * 1000)
        return int(float(re.sub(r'[^\d.]', '', val_str) or 0))
    
    async def _update_energy(self, page):
        """Update energy from top bar - FAST version."""
        try:
            # Use JavaScript to find energy text with multiple selectors
            energy_text = await page.evaluate('''() => {
                const selectors = [
                    '.top-energy-text',
                    '.energy-text',
                    '[class*="energy"][class*="text"]',
                    '.header-energy',
                    '.top-bar-energy'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.textContent) {
                        return el.textContent.trim();
                    }
                }
                return null;
            }''')
            
            if energy_text:
                self._parse_energy(energy_text)
                print(f"[GameState] Energy read: {energy_text} -> current={self.energy_current}, max={self.energy_max}")
        except Exception as e:
            print(f"[GameState] _update_energy ERROR: {e}")
    
    def _parse_energy(self, energy_text: str):
        """Parse energy text like '19.9/20' or '20 (6:00)'."""
        try:
            energy_text = re.sub(r'\s+', ' ', energy_text.replace('\n', ' ')).strip()
            
            if '/' in energy_text:
                parts = energy_text.split('/')
                self.energy_current = float(parts[0].strip())
                tot_part = parts[1].strip()
                if '(' in tot_part:
                    tot_str = tot_part.split('(')[0].strip()
                    self.energy_timer = tot_part.split('(')[1].replace(')', '').strip()
                    self.energy_max = float(tot_str)
                else:
                    self.energy_max = float(tot_part.strip())
            else:
                parts = energy_text.split(' ')
                self.energy_current = float(parts[0].strip())
                if len(parts) > 1:
                    second = parts[1].strip()
                    if ':' in second or second.startswith('-'):
                        self.energy_timer = second
                        # Don't default to 20, use current if max not provided
                        self.energy_max = self.energy_current
                    else:
                        try:
                            self.energy_max = float(second)
                        except:
                            self.energy_max = self.energy_current
                else:
                    self.energy_max = self.energy_current
            
            if self.energy_max > 0:
                self.energy_progress = min(1.0, self.energy_current / self.energy_max)
        except:
            pass
    
    async def _update_currency(self, page):
        """Update bronze, tlrpg, balance - FAST version."""
        # Single JS call to get all currencies at once
        try:
            print("[GameState] _update_currency START")
            currencies = await page.evaluate(r'''() => {
                const result = {};
                // Use actual selectors from the game
                const bronze = document.querySelector('.th-currency[title="Bronze"] .th-currency__value');
                const tlrpg = document.querySelector('.th-currency--tlrpg .th-currency__value');
                const eur = document.querySelector('.th-currency--tlrpg .th-currency__eur');
                const balance = document.querySelector('.th-currency[title="EUR Balance"] .th-currency__value');
                
                if (bronze) result.bronze = bronze.textContent.trim();
                if (tlrpg) result.tlrpg = tlrpg.textContent.trim();
                if (eur) result.eur = eur.textContent.trim();
                if (balance) result.balance = balance.textContent.trim();
                
                // Debug: log what was found
                result.debug = {
                    bronzeFound: !!bronze,
                    tlrpgFound: !!tlrpg,
                    eurFound: !!eur,
                    balanceFound: !!balance
                };
                return result;
            }''')
            
            print(f"[GameState] Currency debug: {currencies.get('debug', {})}")
            
            if 'bronze' in currencies and currencies['bronze']:
                self.bronze = int(currencies['bronze'].replace(",", "").replace(" ", ""))
                print(f"[GameState] Bronze: {self.bronze}")
            else:
                print("[GameState] Bronze not found")
            if 'tlrpg' in currencies and currencies['tlrpg']:
                self.tlrpg = float(currencies['tlrpg'].replace(",", ""))
                print(f"[GameState] TLRPG: {self.tlrpg}")
            if 'eur' in currencies and currencies['eur']:
                self.tlrpg_eur = currencies['eur'].replace("≈€", "").replace("€", "").strip()
                print(f"[GameState] TLRPG/EUR: {self.tlrpg_eur}")
            if 'balance' in currencies and currencies['balance']:
                self.balance = currencies['balance']
        except:
            pass
    
    async def _update_materials(self, page):
        """Update material counts from mobile bottom bar - FAST single-call version."""
        print("[GameState] _update_materials START")
        self.materials = {}
        
        try:
            # Single JavaScript call to parse mobile bottom bar materials
            result = await page.evaluate(r'''() => {
                const result = {};
                const debug = { coreFound: 0, rareFound: 0 };
                
                // Map emoji icons to material names
                const iconMap = {
                    '🌲': 'Wood',
                    '🌾': 'Wheat', 
                    '🪨': 'Rock',
                    '🍖': 'Food',
                    '🧵': 'Cloth'
                };
                
                // Parse core materials from mobile bottom bar
                const coreItems = document.querySelectorAll('.th-mobile-bottom__res-item');
                debug.coreFound = coreItems.length;
                
                coreItems.forEach(item => {
                    const iconSpan = item.querySelector('.th-mobile-bottom__res-icon');
                    const valueSpan = item.querySelector('.th-mobile-bottom__res-val');
                    
                    if (iconSpan && valueSpan) {
                        const icon = iconSpan.textContent.trim();
                        const value = valueSpan.textContent.trim();
                        const materialName = iconMap[icon];
                        if (materialName && value) {
                            result[materialName] = value;
                        }
                    }
                });
                
                // Parse rare materials from rare grid
                const rareItems = document.querySelectorAll('.th-mobile-bottom__rare-grid .th-mobile-bottom__res-item');
                debug.rareFound = rareItems.length;
                
                rareItems.forEach(item => {
                    const img = item.querySelector('.th-mobile-bottom__rare-icon');
                    const valueSpan = item.querySelector('.th-mobile-bottom__res-val');
                    
                    if (img && valueSpan) {
                        // Extract material name from image src or alt
                        const src = img.getAttribute('src') || '';
                        const alt = img.getAttribute('alt') || '';
                        const value = valueSpan.textContent.trim();
                        
                        // Parse name from src like /public/images/rareresources/Ember.png
                        let name = alt;
                        if (!name && src) {
                            const match = src.match(/\/([^\/]+)\.png$/i);
                            if (match) {
                                name = match[1];
                            }
                        }
                        
                        if (name && value) {
                            result[name] = value;
                        }
                    }
                });
                
                result._debug = debug;
                return result;
            }''')
            
            debug_info = result.pop('_debug', {})
            print(f"[GameState] Materials debug: {debug_info}")
            
            # Filter to only the materials we care about
            for mat in self.MATERIAL_NAMES + self.RARE_MATERIALS:
                if mat in result:
                    self.materials[mat] = result[mat]
            
            print(f"[GameState] _update_materials COMPLETED - found {len(self.materials)} materials: {list(self.materials.keys())}")
        except Exception as e:
            print(f"[GameState] _update_materials ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        return self.materials
    
    async def _update_screen_states(self, page):
        """Check for popups, rewards, maintenance."""
        try:
            self.has_reward_screen = await page.locator(".slot-chest-reward-dismiss").count() > 0
        except:
            self.has_reward_screen = False
        
        try:
            self.has_bonus_round = await page.locator(".slot-open-bonus").count() > 0
        except:
            self.has_bonus_round = False
        
        try:
            self.has_energy_popup = await page.locator(".low-energy-popup-overlay").count() > 0
        except:
            self.has_energy_popup = False
        
        try:
            self.has_easter_popup = await page.locator(".easter-popup-overlay, .holiday-popup-overlay, .event-popup-overlay").count() > 0
        except:
            self.has_easter_popup = False
        
        try:
            maintenance_count = await page.locator("text=Maintenance Mode").count()
            maintenance_count += await page.locator("text=We'll Be Right Back").count()
            html = await page.content()
            self.is_maintenance = maintenance_count > 0 or "maintenancePulse" in html
        except:
            self.is_maintenance = False
    
    async def update_battle_state(self, page):
        """Update battle-specific state (call when on battle page)."""
        try:
            # Detect page state
            selectors = {
                "flee": "text=Are you sure you want to flee?",
                "pre_battle_boosts": ".b3b-panel",
                "post_battle_screen": ".b3-post-battle-screen",
                "clue_search": ".clue-search-section",
                "post_battle_modal": ".post-battle-modal",
                "mode_cards": ".battle-mode-cards",
                "stage_card": ".stage-card",
                "bounty_board": ".bounty-board",
                "pb2_actions": ".pb2-actions",
                "wb4_panel": ".b4-hotbar-overlay, .wb4-sidebar-panel, .wb4-skills, .wb4-theater",
                "arena": ".arena-container"
            }
            
            found = []
            for name, selector in selectors.items():
                try:
                    if await page.locator(selector).count() > 0:
                        found.append(name)
                except:
                    pass
            
            # Determine state
            if "flee" in found:
                self.battle.state = "flee_confirmation"
            elif await page.locator(".b3-post-battle-screen").count() > 0:
                if await page.locator(".b3-post-btn-next").count() > 0:
                    self.battle.state = "post_battle_victory"
                elif await page.locator(".b3-reward-total").count() > 0:
                    self.battle.state = "post_battle_rewards"
                else:
                    self.battle.state = "post_battle"
            elif await page.locator(".b3b-panel").count() > 0:
                self.battle.state = "pre_battle_boosts"
            elif await page.locator(".battle-mode-cards").count() > 0:
                self.battle.state = "mode_selection"
            elif await page.locator(".stage-card").count() > 0 and await page.locator(".bounty-board").count() > 0:
                self.battle.state = "stage_hub"
            elif await page.locator(".pb2-actions").count() > 0:
                self.battle.state = "battle_preview"
            elif await page.locator(".b4-hotbar-overlay, .wb4-sidebar-panel, .wb4-skills, .wb4-theater").count() > 0:
                self.battle.state = "battle_arena"
                self.battle.has_active_battle = True
            else:
                self.battle.state = "unknown"
            
            # Get stage name
            for selector in [".stage-name", ".bounty-stage-name", "h2.stage-title", ".stage-info h3"]:
                try:
                    stage_text = await page.inner_text(selector, timeout=1000)
                    if stage_text:
                        self.battle.current_stage = stage_text.strip()
                        break
                except:
                    pass
            
            # Get kills
            for selector in [".total-kills .value", ".kills-count", ".battle-kills", ".kill-counter"]:
                try:
                    kills = await page.inner_text(selector, timeout=1000)
                    if kills:
                        self.battle.kills = int(re.sub(r'[^\d]', '', kills))
                        break
                except:
                    pass
            
            # Get available skills if in battle
            if self.battle.state == "battle_arena":
                self.battle.available_skills = []
                skill_buttons = page.locator(".b4-skill:not(.flee):not([disabled]), .wb4-skill:not(.wb4-skill-empty):not(.wb4-skill-flee):not([disabled])")
                for i in range(await skill_buttons.count()):
                    btn = skill_buttons.nth(i)
                    try:
                        if await btn.is_visible():
                            name_elem = btn.locator(".b4-skill-name, .wb4-sk-name")
                            if await name_elem.count() > 0:
                                name = await name_elem.inner_text(timeout=1000)
                            else:
                                name = await btn.get_attribute("title") or ""
                            if name and name not in ["Not Equipped", "Run", "RUN", "", None]:
                                self.battle.available_skills.append((name, btn))
                    except:
                        pass
        except Exception as e:
            print(f"[GameState] Battle update error: {e}")
    
    async def _update_battle_details(self, page):
        """Enhanced battle data scraping - stats, streak, bounty, HP from new battle panel."""
        try:
            # New battle panel structure - get stats from b3-combat-stats
            # HP stat card - icon is ❤️
            hp_card = page.locator('.b3-stat-card:has(.b3-stat-icon:has-text("❤️"))').first
            if await hp_card.count() > 0:
                hp_total = await hp_card.locator('.b3-stat-total').inner_text()
                if hp_total:
                    self.player_stats.hp_current = int(re.sub(r'[^\d]', '', hp_total))
                    # Also get breakdown for max HP if available
                    hp_breakdown = await hp_card.locator('.b3-stat-breakdown').inner_text()
                    if hp_breakdown and '+' in hp_breakdown:
                        # Format: "2,033+3,298" - total is already in hp_total
                        pass
            
            # ATK stat card - icon is ⚔️
            atk_card = page.locator('.b3-stat-card:has(.b3-stat-icon:has-text("⚔️"))').first
            if await atk_card.count() > 0:
                atk_total = await atk_card.locator('.b3-stat-total').inner_text()
                if atk_total:
                    self.player_stats.total_attack = int(re.sub(r'[^\d]', '', atk_total))
            
            # DEF stat card - icon is 🛡️
            def_card = page.locator('.b3-stat-card:has(.b3-stat-icon:has-text("🛡️"))').first
            if await def_card.count() > 0:
                def_total = await def_card.locator('.b3-stat-total').inner_text()
                if def_total:
                    self.player_stats.total_defense = int(re.sub(r'[^\d]', '', def_total))
            
            # Fallback to old selectors for compatibility
            if not hasattr(self.player_stats, 'hp_current') or self.player_stats.hp_current == 0:
                stat_selectors = {
                    'hp_current': ['.hp-value', '.health-text', '.player-hp', '.current-hp'],
                }
                for stat_name, selectors in stat_selectors.items():
                    for selector in selectors:
                        try:
                            loc = page.locator(selector)
                            if await loc.count() > 0:
                                val = await loc.first.inner_text(timeout=300)
                                if val and '/' in val:
                                    parts = val.split('/')
                                    self.player_stats.hp_current = int(re.sub(r'[^\d]', '', parts[0]))
                                    self.player_stats.hp_max = int(re.sub(r'[^\d]', '', parts[1]))
                                    break
                        except:
                            pass
            
            # Get current streak from bb-kill-rank
            kr_elem = page.locator('.bb-kr-main').first
            if await kr_elem.count() > 0:
                kr_text = await kr_elem.inner_text()
                # Parse "🏆 TOP 364 · 1,047 kills"
                kills_match = re.search(r'([\d,]+)\s+kills', kr_text)
                if kills_match:
                    self.battle.kills = int(kills_match.group(1).replace(',', ''))
                # Also parse rank
                rank_match = re.search(r'TOP\s+(\d+)', kr_text)
                if rank_match:
                    self.battle.current_rank = int(rank_match.group(1))
            
            # Get stage name
            stage_elem = page.locator('.stage-header h1').first
            if await stage_elem.count() > 0:
                self.battle.stage_name = await stage_elem.inner_text()
            
            # Get bounty board info
            bounty_rows = await page.locator('.bounty-row').all()
            self.battle.bounties = {}
            for row in bounty_rows:
                try:
                    label = await row.locator('.bounty-label').inner_text()
                    count = await row.locator('.bounty-count').inner_text()
                    self.battle.bounties[label.lower()] = count
                except:
                    pass
                        
        except Exception as e:
            pass  # Silently fail for optional details
    
    async def update_quests(self, page):
        """Parse daily quests from battle page."""
        try:
            self.daily_quests = []
            quest_cards = await page.locator('.dq-card').all()
            
            for i, card in enumerate(quest_cards):
                try:
                    # Get quest name
                    name_elem = card.locator('span').nth(2)  # Third span is the name
                    name = await name_elem.inner_text() if await name_elem.count() > 0 else f"Quest {i+1}"
                    
                    # Check for claimable status (has claim button)
                    claim_btn = card.locator('.dq-claim-button').first
                    can_claim = await claim_btn.count() > 0
                    
                    # Check for completed status (has ✅ or green border)
                    is_completed = 'border: 1px solid rgba(34, 197, 94' in await card.evaluate('el => el.style.cssText + el.outerHTML') or \
                                  await card.locator('text=✅').count() > 0 or \
                                  await card.locator('text=Collected!').count() > 0
                    
                    # Get progress percentage from circle stroke
                    circle = card.locator('circle[stroke-dasharray]').nth(1)
                    progress_pct = 0
                    if await circle.count() > 0:
                        dasharray = await circle.get_attribute('stroke-dasharray')
                        if dasharray:
                            parts = dasharray.split()
                            if len(parts) == 2:
                                filled = float(parts[0])
                                total = float(parts[1])
                                progress_pct = int((filled / total) * 100) if total > 0 else 0
                    
                    # Get reward text
                    reward_elem = card.locator('span:has-text("Win:")').first
                    reward = await reward_elem.inner_text() if await reward_elem.count() > 0 else ""
                    
                    # Get description/progress text
                    desc_elem = card.locator('span:has-text("/")').first  # e.g., "63 / 250 kills"
                    if await desc_elem.count() == 0:
                        desc_elem = card.locator('span:has-text("kills")').first
                    description = await desc_elem.inner_text() if await desc_elem.count() > 0 else ""
                    
                    # Determine status
                    if can_claim:
                        status = "claimable"
                    elif is_completed or progress_pct >= 100:
                        status = "completed"
                    else:
                        status = "in_progress"
                    
                    quest = Quest(
                        name=name,
                        progress_pct=progress_pct,
                        status=status,
                        reward=reward,
                        description=description,
                        can_claim=can_claim,
                        button_selector=f'.dq-card >> nth={i} >> .dq-claim-button' if can_claim else ""
                    )
                    self.daily_quests.append(quest)
                    print(f"[GameState] Quest: {name} - {status} ({progress_pct}%)")
                    
                except Exception as e:
                    print(f"[GameState] Error parsing quest {i}: {e}")
                    continue
                    
            print(f"[GameState] Found {len(self.daily_quests)} daily quests")
            
        except Exception as e:
            print(f"[GameState] Quest update error: {e}")
    
    async def update_chests(self, page):
        """Update chest availability (call when on chests page)."""
        try:
            # Get bronze from chests page
            wallet = page.locator(".sc-wallet-val").first
            if await wallet.count() > 0:
                brz_text = await wallet.inner_text()
                self.current_bronze = int(brz_text.replace(",", "").replace(" ", ""))
            
            self.chests = []
            cards = page.locator(".sc-chest-card")
            for i in range(await cards.count()):
                card = cards.nth(i)
                try:
                    name_elem = card.locator(".chest-name, .sc-chest-name")
                    if await name_elem.count() > 0:
                        name = await name_elem.inner_text()
                        category = "Resource" if "Chest" in name else "Armory"
                        classes = await card.evaluate("node => node.className")
                        
                        # NEW: Get bronze cost
                        bronze_cost = 0
                        cost_selectors = ['.chest-cost', '.bronze-cost', '.sc-cost-value', '.cost-amount']
                        for cost_sel in cost_selectors:
                            try:
                                cost_elem = card.locator(cost_sel).first
                                if await cost_elem.count() > 0:
                                    cost_text = await cost_elem.inner_text()
                                    bronze_cost = int(re.sub(r'[^\d]', '', cost_text))
                                    if bronze_cost > 0:
                                        break
                            except:
                                pass
                        
                        # NEW: Get cooldown time
                        cooldown_time = ""
                        if "on-cooldown" in classes:
                            cd_selectors = ['.cooldown-timer', '.chest-cooldown', '.timer-text', '.cooldown-text']
                            for cd_sel in cd_selectors:
                                try:
                                    cd_elem = card.locator(cd_sel).first
                                    if await cd_elem.count() > 0:
                                        cooldown_time = await cd_elem.inner_text()
                                        if cooldown_time:
                                            break
                                except:
                                    pass
                            if not cooldown_time:
                                cooldown_time = "On Cooldown"
                        else:
                            cooldown_time = "Ready"
                        
                        chest = ChestInfo(
                            name=name.strip(),
                            category=category,
                            is_locked="locked" in classes,
                            is_tlrpg_only="tlrpg-only" in classes,
                            is_on_cooldown="on-cooldown" in classes,
                            can_summon=not any(x in classes for x in ["locked", "tlrpg-only", "on-cooldown"]),
                            bronze_cost=bronze_cost,
                            cooldown_time=cooldown_time
                        )
                        self.chests.append(chest)
                except:
                    pass
        except Exception as e:
            print(f"[GameState] Chests update error: {e}")
    
    async def update_business(self, page):
        """Update business state (call when on businesses page)."""
        try:
            print("[GameState] update_business START")
            # Bronze bank - try new UI selector first, then old selector, then JavaScript fallback
            # New UI: .b3d-hud__bar-text contains "1,587 / 17,695 bronze"
            bank_val_el = page.locator(".b3d-hud__bar-text")
            if await bank_val_el.count() > 0:
                raw_val = await bank_val_el.first.inner_text()
                # Extract the amount (e.g., "1,587 / 17,695 bronze" -> "1,587")
                import re
                match = re.search(r'([\d,]+)\s*\/', raw_val)
                if match:
                    self.business.stored_bronze = self._parse_bank_amount(match.group(1))
                    # Also populate business_stored for business worker compatibility
                    self.business_stored["bronze"] = self.business.stored_bronze
                    print(f"[GameState] Bronze bank (new UI): {self.business.stored_bronze}")
                else:
                    print(f"[GameState] Bronze bank (new UI) - couldn't parse: {raw_val}")
            else:
                # Try old selector
                bank_val_el = page.locator("section.bronze-bank-section .bank-amount-value")
                bank_cap_el = page.locator("section.bronze-bank-section .bank-capacity")
                
                if await bank_val_el.count() > 0:
                    raw_val = await bank_val_el.first.inner_text()
                    self.business.stored_bronze = self._parse_bank_amount(raw_val)
                    # Also populate business_stored for business worker compatibility
                    self.business_stored["bronze"] = self.business.stored_bronze
                    print(f"[GameState] Bronze bank (old UI selector): {self.business.stored_bronze}")
                else:
                    # Try JavaScript fallback
                    try:
                        bank_info = await page.evaluate(r'''() => {
                            const result = {};
                            const bankSection = document.querySelector('section.bronze-bank-section');
                            if (bankSection) {
                                const valEl = bankSection.querySelector('.bank-amount-value');
                                const capEl = bankSection.querySelector('.bank-capacity');
                                if (valEl) result.value = valEl.textContent.trim();
                                if (capEl) result.capacity = capEl.textContent.trim();
                            }
                            return result;
                        }''')
                        if 'value' in bank_info and bank_info['value']:
                            self.business.stored_bronze = self._parse_bank_amount(bank_info['value'])
                            self.business_stored["bronze"] = self.business.stored_bronze
                            print(f"[GameState] Bronze bank (JS): {self.business.stored_bronze}")
                        else:
                            print("[GameState] Bronze bank value not found (JS)")
                    except:
                        print("[GameState] Bronze bank value not found")
            
            # Try to get capacity from new UI or old UI
            bank_cap_el = page.locator(".b3d-hud__bar-text")
            if await bank_cap_el.count() > 0:
                raw_cap = await bank_cap_el.first.inner_text()
                # Extract capacity (e.g., "1,587 / 17,695 bronze" -> "17,695")
                import re
                match = re.search(r'\/\s*([\d,]+)', raw_cap)
                if match:
                    self.business.bronze_capacity = self._parse_bank_amount(match.group(1))
                    print(f"[GameState] Bronze capacity (new UI): {self.business.bronze_capacity}")
            else:
                bank_cap_el = page.locator("section.bronze-bank-section .bank-capacity")
                if await bank_cap_el.count() > 0:
                    raw_cap = await bank_cap_el.first.inner_text()
                    self.business.bronze_capacity = self._parse_bank_amount(raw_cap)
                    print(f"[GameState] Bronze capacity (old UI): {self.business.bronze_capacity}")
            
            if self.business.bronze_capacity > 0:
                self.business.bronze_progress = min(1.0, self.business.stored_bronze / self.business.bronze_capacity)
            
            # Materials from DOM - try new UI first, then old UI
            dom_map = await page.evaluate("""() => {
                const out = {};
                // Try new UI: .b3d-lbl elements with .b3d-lbl__amt
                const newNodes = document.querySelectorAll('.b3d-lbl');
                if (newNodes.length > 0) {
                    for (const el of newNodes) {
                        const nameEl = el.querySelector('.b3d-lbl__name');
                        const amtEl = el.querySelector('.b3d-lbl__amt');
                        if (nameEl && amtEl) {
                            const name = nameEl.innerText.trim();
                            const stored = amtEl.innerText.trim();
                            if (name && stored) out[name] = stored;
                        }
                    }
                }
                // Fallback to old UI
                if (Object.keys(out).length === 0) {
                    const nodes = document.querySelectorAll('.business-row-stored');
                    for (const el of nodes) {
                        const stored = el.innerText.trim();
                        if (!stored) continue;
                        let row = el.closest('.business-row, .business-card, [class*="business-row"], tr, section');
                        if (!row) row = el.parentElement;
                        let name = '';
                        const prefer = row.querySelector(
                            '[class*="name"]:not(.business-row-stored), [data-resource], [data-material], h3, h4, h5, .business-name, .material-name'
                        );
                        if (prefer) {
                            name = prefer.innerText.trim().split(/\\s+/).slice(0, 4).join(' ');
                        }
                        if (!name) {
                            const chunks = row.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
                            for (const c of chunks) {
                                if (c === stored || stored.includes(c) || c.includes('/')) continue;
                                if (c.length > 0 && c.length < 40 && !/^\\d/.test(c)) {
                                    name = c.split(/\\s+/)[0];
                                    break;
                                }
                            }
                        }
                        name = (name || 'Unknown').trim();
                        if (name && name !== 'Unknown') out[name] = stored;
                    }
                }
                return out;
            }""")
            
            # NEW: Track which materials are ready for collection
            self.business.materials_ready = []
            has_any_ready = self.business.stored_bronze > 0
            
            for mat in self.MATERIAL_NAMES:
                val = None
                mn = self._norm(mat)
                for k, v in dom_map.items():
                    kn = self._norm(k)
                    if kn == mn or mn in kn or kn in mn or kn.startswith(mn):
                        val = v
                        break
                
                if val:
                    a, b = self._parse_slash_pair(val)
                    self.business.stored_materials[mat] = (a or 0, b or 0)
                    # Also populate business_stored for business worker compatibility
                    self.business_stored[mat] = a or 0
                    if b and b > 0:
                        self.business.material_progress[mat] = min(1.0, a / b)
                        # Check if this material is ready to collect
                        if a > 0:
                            self.business.materials_ready.append(mat)
                            has_any_ready = True
            
            # NEW: Update collection status
            self.business.collection_ready = has_any_ready
            
            # NEW: Try to get next collection time
            try:
                next_time_elem = page.locator('.next-collection-time, .collection-timer, .next-available-time').first
                if await next_time_elem.count() > 0:
                    self.business.next_collection_time = await next_time_elem.inner_text()
                else:
                    self.business.next_collection_time = ""
            except:
                self.business.next_collection_time = ""
                
        except Exception as e:
            print(f"[GameState] Business update error: {e}")
    
    def _parse_bank_amount(self, text: str) -> int:
        """Parse bronze bank amount."""
        if not text:
            return 0
        whole_part = text.split('.')[0]
        clean_text = "".join(re.findall(r"\d+", whole_part))
        return int(clean_text) if clean_text else 0
    
    def _parse_slash_pair(self, text: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse 'current/max' format."""
        if not text:
            return None, None
        m = re.match(r"([\d,]+)\s*/\s*([\d,]+)", text.strip())
        if not m:
            return None, None
        a = int(m.group(1).replace(",", ""))
        b = int(m.group(2).replace(",", ""))
        return a, b
    
    def _norm(self, s: str) -> str:
        """Normalize string for comparison."""
        return re.sub(r"\s+", " ", (s or "").strip().lower())
    
    async def update_chests_state(self, page) -> bool:
        """Update chest state from the chests page. Called by brain during chest operations."""
        try:
            print("[GameState] update_chests_state START")
            
            # Clear old chest data
            self.chests.clear()
            
            # Find all chest cards using new HTML structure
            chest_cards = await page.locator('.sc-chest-card').all()
            print(f"[GameState] Found {len(chest_cards)} chest cards")
            
            for card in chest_cards:
                try:
                    # Get chest name
                    name_elem = card.locator('.sc-chest-name').first
                    name = await name_elem.inner_text() if await name_elem.count() > 0 else ""
                    name = name.strip()
                    
                    if not name:
                        continue
                    
                    # Determine category based on name
                    category = "Resource" if "Chest" in name else "Armory" if "Armory" in name else "Other"
                    
                    # Check if chest is locked
                    is_locked = await card.locator('.locked').count() > 0
                    
                    # Get cost - prefer bronze cost, fallback to TLRPG
                    cost = 0
                    cost_text = ""
                    
                    # Try to get bronze price first
                    bronze_elem = card.locator('.sc-price-bronze').first
                    if await bronze_elem.count() > 0:
                        bronze_text = await bronze_elem.inner_text()
                        # Extract number after 🪙
                        cost = self._parse_number(bronze_text)
                    
                    # If no bronze price, try TLRPG price
                    if cost == 0:
                        tlrpg_elem = card.locator('.sc-price-tlrpg').first
                        if await tlrpg_elem.count() > 0:
                            tlrpg_text = await tlrpg_elem.inner_text()
                            cost = self._parse_number(tlrpg_text)
                    
                    # Check if TLRPG only (no bronze option)
                    is_tlrpg_only = await card.locator('.tlrpg-only').count() > 0
                    
                    # Determine if can summon
                    # Can summon if not locked, has a valid cost, and not on cooldown
                    can_summon = not is_locked and cost > 0
                    cooldown = ""
                    
                    # Check for cooldown timer (some chests have cooldown even if not locked)
                    cooldown_elem = card.locator('.sc-cooldown-timer, .sc-timer, [class*="cooldown"], [class*="timer"]')
                    if await cooldown_elem.count() > 0:
                        cooldown_text = await cooldown_elem.first.inner_text()
                        if cooldown_text and cooldown_text.strip():
                            cooldown = cooldown_text.strip()
                            can_summon = False  # Chest is on cooldown
                            print(f"[GameState] Chest {name} on cooldown: {cooldown}")
                    
                    # Also check if summon button is disabled
                    summon_btn = card.locator('.sc-chest-summon-btn, button:has-text("Summon"), button:has-text("OPEN")')
                    if await summon_btn.count() > 0:
                        is_disabled = await summon_btn.first.is_disabled()
                        if is_disabled:
                            can_summon = False
                            cooldown = "Button disabled"
                            print(f"[GameState] Chest {name} summon button disabled")
                    
                    if is_locked:
                        # Get lock reason text
                        lock_elem = card.locator('.sc-locked-text').first
                        cooldown = await lock_elem.inner_text() if await lock_elem.count() > 0 else "Locked"
                        can_summon = False
                    
                    chest_info = ChestInfo(
                        name=name,
                        category=category,
                        bronze_cost=cost,
                        can_summon=can_summon,
                        cooldown_time=cooldown
                    )
                    self.chests.append(chest_info)
                    print(f"[GameState] Chest: {name} ({category}) - Cost: {cost}, Locked: {is_locked}, Can summon: {can_summon}")
                    
                except Exception as e:
                    print(f"[GameState] Error parsing chest card: {e}")
                    continue
            
            available_count = len([c for c in self.chests if c.can_summon])
            print(f"[GameState] update_chests_state COMPLETED - {len(self.chests)} chests, {available_count} available")
            return True
            
        except Exception as e:
            print(f"[GameState] update_chests_state ERROR: {e}")
            return False
    
    def get_available_chests(self, category: str = None) -> List[ChestInfo]:
        """Get list of chests that can be summoned."""
        available = [c for c in self.chests if c.can_summon]
        if category:
            available = [c for c in available if c.category == category]
        return available
    
    def has_pending_collections(self) -> bool:
        """Check if any business collections are ready."""
        if self.business.stored_bronze > 0:
            return True
        for mat, (current, max_val) in self.business.stored_materials.items():
            if current > 0:
                return True
        return False
