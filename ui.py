"""UI - Main user interface for TokenLords Bot."""
import asyncio
import customtkinter as ctk
import threading
import queue
import time
from typing import Callable, Optional
from datetime import datetime

# Creator name constant
CREATOR_NAME = "Touched"
APP_VERSION = "v1.2"


class TokenLordsUI(ctk.CTk):
    """Main UI window with compact structure:
    1. Title Bar (with creator name)
    2. Info Bar (Name/Class | Lvl | XP | Energy | Theme Toggle)
    3. Materials Bar (2 rows: Core row 1, Rare row 2)
    4. Tabs (General/Battle/Chests/Business)
       - General: Master Controls + Log Area
    5. Status Bar (bottom)
    """
    
    # Theme color definitions
    THEMES = {
        "dark": {
            "bg_primary": "#1a1a1a",
            "bg_secondary": "#2c3e50",
            "bg_tertiary": "#0d0d0d",
            "text_primary": "#ffffff",
            "text_secondary": "#cccccc",
            "text_muted": "#7f8c8d",
            "accent_gold": "#F7A00F",
            "accent_blue": "#3498db",
            "accent_green": "#27ae60",
            "accent_red": "#e74c3c",
            "accent_purple": "#9b59b6",
            "accent_orange": "#e67e22",
            "accent_cyan": "#87CEEB",
            "progress_bg": "#333333",
            "border_color": "#444444",
            "tab_selected": "#F7A00F"
        },
        "light": {
            "bg_primary": "#f5f5f5",
            "bg_secondary": "#e0e0e0",
            "bg_tertiary": "#ffffff",
            "text_primary": "#2c3e50",
            "text_secondary": "#34495e",
            "text_muted": "#7f8c8d",
            "accent_gold": "#d68910",
            "accent_blue": "#2980b9",
            "accent_green": "#229954",
            "accent_red": "#c0392b",
            "accent_purple": "#8e44ad",
            "accent_orange": "#d35400",
            "accent_cyan": "#16a085",
            "progress_bg": "#bdc3c7",
            "border_color": "#95a5a6",
            "tab_selected": "#d68910"
        }
    }
    
    def __init__(self, brain):
        super().__init__()
        
        self.brain = brain
        self.brain.ui_callback = self._on_state_update
        
        # Command queue for Playwright execution (brain -> main thread)
        import queue
        self.command_queue = queue.Queue()
        self.result_queue = queue.Queue()
        # Set command queue on brain
        self.brain.command_queue = self.command_queue
        
        self.current_theme = brain.settings.get("general.theme", "dark")
        self.colors = self.THEMES[self.current_theme]
        
        # Apply theme to customtkinter
        ctk.set_appearance_mode(self.current_theme)
        
        self.title(f"TokenLords Bot {APP_VERSION} - by {CREATOR_NAME}")
        self.geometry("950x680")  # Smaller window
        
        # Log queue for thread-safe logging
        self.log_queue = queue.Queue()
        self.log_running = False
        self.log_file = None
        
        # 1. Info Bar - Compact character info
        self._create_info_bar()
        
        # 2. Materials Bar - 2 rows (Core + Rare)
        self._create_materials_bar()
        
        # 3. Control Buttons Bar (Hook, Launch, Start, Start Logging)
        self._create_controls_bar()
        
        # 4. Tabs - General (master controls+log), Battle, Chests, Business
        self.tabs = ctk.CTkTabview(self, segmented_button_selected_color=self.colors["tab_selected"], height=320)
        self.tabs._segmented_button.configure(font=("Arial", 14, "bold"), width=120)
        self.tabs.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.tab_general = self._create_general_tab()
        self.tab_battle = self._create_battle_tab()
        self.tab_chests = self._create_chests_tab()
        self.tab_business = self._create_business_tab()
        
        # 4. Status Bar - Bottom
        self._create_status_bar()
        
        self._load_settings_into_ui()
        
        # Start UI update loops
        self.after(1000, self._update_ui)
        self.after(100, self._process_log_queue)
    
    def _process_log_queue(self):
        """Process log queue entries and display them in the log text area."""
        try:
            while not self.log_queue.empty():
                message = self.log_queue.get_nowait()
                self._append_log_message(message)
        except:
            pass
        # Schedule next check
        self.after(100, self._process_log_queue)
    
    def _append_log_message(self, message: str):
        """Append a message to the log text area."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        
        # Also write to file if logging is enabled
        if self.log_running and self.log_file:
            try:
                self.log_file.write(message + "\n")
                self.log_file.flush()
            except:
                pass
    
    def _load_settings_into_ui(self):
        """Load saved settings into UI controls on startup."""
        s = self.brain.settings
        
        # Master controls
        if s.battle_enabled:
            self.chk_master_battle.select()
        if s.chests_enabled:
            self.chk_master_chests.select()
        if s.business_enabled:
            self.chk_master_business.select()
            # Also check the sub-checkbox
            if s.get("business.auto_collect", False):
                self.chk_auto_collect.select()
        
        # Battle tab
        if s.battle_enabled:
            self.chk_battle_auto.select()
        
        # Chests tab
        if s.chests_enabled:
            self.chk_chests_auto.select()
        
        # Auto-claim quests - load from settings
        if s.get("auto_claim_quests", False):
            self.chk_auto_claim_quests.select()
        
        # Skill priority - load from settings
        saved_skills = s.get("battle.skill_priority", ["Attack", "none", "none", "none", "none", "none"])
        last_skill_names = s.get("battle.last_skill_names", [])
        
        # Update skills_list with detected skills if available
        if last_skill_names:
            # Build skills_list from detected skills + common options
            skills_list = list(set(last_skill_names + ["Attack", "none"]))
            skills_list.sort()
        else:
            skills_list = ["Attack", "Guard", "Cry", "Power", "Dodge", "Poison", "Run", "none"]
        
        # Update dropdown values if they exist
        if hasattr(self, 'skill_vars'):
            for i in range(6):
                if i < len(saved_skills):
                    self.skill_vars[f"slot_{i}"].set(saved_skills[i])
                else:
                    self.skill_vars[f"slot_{i}"].set("none")
    
    def _create_info_bar(self):
        """Create 6-column info bar with exact layout."""
        self.info_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_primary"], height=45)
        self.info_frame.pack(fill="x", padx=15, pady=(10, 5))
        self.info_frame.pack_propagate(False)
        
        # Main container
        main_grid = ctk.CTkFrame(self.info_frame, fg_color="transparent")
        main_grid.pack(fill="both", expand=True, padx=5, pady=2)
        main_grid.grid_columnconfigure((0, 1, 2, 3, 4), weight=0)
        main_grid.grid_rowconfigure(0, weight=1)
        
        # Column 0: Name + Class under it
        name_frame = ctk.CTkFrame(main_grid, fg_color="transparent", width=140, height=40)
        name_frame.grid(row=0, column=0, sticky="w", padx=(0, 5))
        name_frame.grid_propagate(False)
        
        self.lbl_user = ctk.CTkLabel(
            name_frame, text="Not Connected",
            font=("Arial", 14, "bold"),
            text_color=self.colors["accent_gold"]
        )
        self.lbl_user.place(x=0, y=0)
        
        self.lbl_class = ctk.CTkLabel(
            name_frame, text="",
            font=("Arial", 11),
            text_color=self.colors["text_muted"]
        )
        self.lbl_class.place(x=0, y=18)
        
        # Column 1: Level + XP numbers, XP bar under
        lvl_frame = ctk.CTkFrame(main_grid, fg_color="transparent", width=160, height=40)
        lvl_frame.grid(row=0, column=1, sticky="w", padx=(0, 5))
        lvl_frame.grid_propagate(False)
        
        self.lbl_level = ctk.CTkLabel(
            lvl_frame, text="LV: --",
            font=("Arial", 12, "bold"),
            text_color=self.colors["accent_blue"]
        )
        self.lbl_level.place(x=0, y=0)
        
        self.lbl_xp = ctk.CTkLabel(
            lvl_frame, text="--/--",
            font=("Arial", 10),
            text_color=self.colors["text_muted"]
        )
        self.lbl_xp.place(x=50, y=2)
        
        self.xp_bar = ctk.CTkProgressBar(
            lvl_frame, width=140, height=5,
            progress_color=self.colors["accent_gold"],
            fg_color=self.colors["progress_bg"]
        )
        self.xp_bar.set(0)
        self.xp_bar.place(x=0, y=20)
        
        # Column 2: Weekly
        weekly_frame = ctk.CTkFrame(main_grid, fg_color="transparent", width=90, height=40)
        weekly_frame.grid(row=0, column=2, sticky="w", padx=(0, 5))
        weekly_frame.grid_propagate(False)
        
        self.lbl_weekly_header = ctk.CTkLabel(
            weekly_frame, text="",
            font=("Arial", 10),
            text_color=self.colors["text_muted"]
        ).place(x=0, y=5)
        
        self.lbl_weekly = ctk.CTkLabel(
            weekly_frame, text="--/--",
            font=("Arial", 11, "bold"),
            text_color=self.colors["accent_gold"]
        )
        self.lbl_weekly.place(x=0, y=20)
        
        # Column 3: Currencies (Bronze, TLRPG, EUR)
        curr_frame = ctk.CTkFrame(main_grid, fg_color="transparent", width=300, height=40)
        curr_frame.grid(row=0, column=3, sticky="w", padx=(0, 5))
        curr_frame.grid_propagate(False)
        
        # Bronze
        ctk.CTkLabel(curr_frame, text="🪙", font=("Arial", 12)).place(x=0, y=8)
        self.lbl_bronze = ctk.CTkLabel(
            curr_frame, text="--", font=("Arial", 11, "bold"),
            text_color=self.colors["accent_gold"], width=70
        )
        self.lbl_bronze.place(x=18, y=8)
        
        # TLRPG
        ctk.CTkLabel(curr_frame, text="💎", font=("Arial", 11)).place(x=90, y=8)
        self.lbl_tlrpg = ctk.CTkLabel(
            curr_frame, text="--", font=("Arial", 10),
            text_color=self.colors["accent_cyan"], width=45
        )
        self.lbl_tlrpg.place(x=106, y=8)
        
        self.lbl_tlrpg_eur = ctk.CTkLabel(
            curr_frame, text="", font=("Arial", 8),
            text_color=self.colors["text_muted"], width=35
        )
        self.lbl_tlrpg_eur.place(x=150, y=10)
        
        # EUR
        ctk.CTkLabel(curr_frame, text="💶", font=("Arial", 11)).place(x=185, y=8)
        self.lbl_eur = ctk.CTkLabel(
            curr_frame, text="--", font=("Arial", 10, "bold"),
            text_color=self.colors["accent_green"], width=55
        )
        self.lbl_eur.place(x=202, y=8)
        
        # Column 4: Energy text + bar next to each other
        energy_frame = ctk.CTkFrame(main_grid, fg_color="transparent", width=180, height=40)
        energy_frame.grid(row=0, column=4, sticky="w", padx=(0, 5))
        energy_frame.grid_propagate(False)
        
        self.lbl_energy_txt = ctk.CTkLabel(
            energy_frame, text="0/0",
            font=("Arial", 12, "bold"),
            text_color=self.colors["accent_cyan"]
        )
        self.lbl_energy_txt.place(x=0, y=10)
        
        self.energy_bar = ctk.CTkProgressBar(
            energy_frame, width=120, height=8,
            progress_color=self.colors["accent_cyan"],
            fg_color=self.colors["progress_bg"]
        )
        self.energy_bar.set(0)
        self.energy_bar.place(x=55, y=13)
    
    def _create_materials_bar(self):
        """Create 2-row materials bar with equal spacing."""
        self.mat_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_secondary"])
        self.mat_frame.pack(fill="x", padx=15, pady=5)
        
        # Row 1: Core materials with equal grid spacing
        row1 = ctk.CTkFrame(self.mat_frame, fg_color="transparent")
        row1.pack(fill="x", padx=5, pady=(5, 2))
        
        # Title column (10% width) + 5 equal columns (18% each)
        row1.grid_columnconfigure(0, weight=1, minsize=60)  # CORE title
        for i in range(1, 6):
            row1.grid_columnconfigure(i, weight=3, minsize=110)  # 5 materials
        
        ctk.CTkLabel(
            row1, text="CORE",
            font=("Arial", 9, "bold"),
            text_color=self.colors["text_muted"]
        ).grid(row=0, column=0, sticky="w", padx=5)
        
        self.mat_labels = {}
        core_materials = [
            ("Wood", "🌲"), ("Wheat", "🌾"), ("Rock", "🪨"),
            ("Food", "🍖"), ("Cloth", "🧵")
        ]
        
        for idx, (name, emoji) in enumerate(core_materials):
            item_frame = ctk.CTkFrame(row1, fg_color="transparent")
            item_frame.grid(row=0, column=idx+1, sticky="w", padx=5)
            
            ctk.CTkLabel(item_frame, text=emoji, font=("Arial", 13)).pack(side="left")
            lbl = ctk.CTkLabel(
                item_frame, text="--", font=("Arial", 12, "bold"),
                text_color=self.colors["accent_gold"], width=55
            )
            lbl.pack(side="left", padx=(2, 0))
            self.mat_labels[name] = lbl
        
        # Row 2: Rare materials with equal grid spacing
        row2 = ctk.CTkFrame(self.mat_frame, fg_color="transparent")
        row2.pack(fill="x", padx=5, pady=(2, 5))
        
        # Title column (8% width) + 10 equal columns (9.2% each)
        row2.grid_columnconfigure(0, weight=1, minsize=50)  # RARE title
        for i in range(1, 11):
            row2.grid_columnconfigure(i, weight=2, minsize=65)  # 10 materials
        
        ctk.CTkLabel(
            row2, text="RARE",
            font=("Arial", 9, "bold"),
            text_color=self.colors["accent_purple"]
        ).grid(row=0, column=0, sticky="w", padx=5)
        
        self.rare_labels = {}
        rare_materials = [
            ("Ember", "🔥"), ("Verdite", "🌿"), ("Moonite", "🌙"),
            ("Stormis", "⚡"), ("Drakon", "🐉"), ("Voidium", "🌑"),
            ("Celest", "⭐"), ("Mythril", "⚔️"), ("Eternium", "♾️"),
            ("Chronis", "⏳")
        ]
        
        for idx, (name, emoji) in enumerate(rare_materials):
            item_frame = ctk.CTkFrame(row2, fg_color="transparent")
            item_frame.grid(row=0, column=idx+1, sticky="w", padx=2)
            
            ctk.CTkLabel(
                item_frame, text=emoji, font=("Arial", 12),
                text_color=self.colors["accent_purple"]
            ).pack(side="left")
            lbl = ctk.CTkLabel(
                item_frame, text="--", font=("Arial", 10),
                text_color=self.colors["accent_gold"], width=40
            )
            lbl.pack(side="left", padx=(1, 0))
            self.rare_labels[name] = lbl
    
    def _create_controls_bar(self):
        """Create control buttons bar (Hook, Launch, Start, Theme, Loot Spins)."""
        ctrl_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_primary"])
        ctrl_frame.pack(fill="x", padx=15, pady=5)
        
        btn_frame = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=8)
        
        self.btn_hook = ctk.CTkButton(
            btn_frame,
            text="🔗 HOOK EDGE",
            font=("Arial", 12, "bold"),
            command=self._on_hook,
            width=130,
            fg_color=self.colors["accent_blue"]
        )
        self.btn_hook.pack(side="left", padx=5)
        
        self.btn_browser = ctk.CTkButton(
            btn_frame,
            text="🌐 LAUNCH EDGE",
            font=("Arial", 12, "bold"),
            command=self._launch_browser,
            width=130,
            fg_color=self.colors["accent_purple"]
        )
        self.btn_browser.pack(side="left", padx=5)
        
        self.btn_start_stop = ctk.CTkButton(
            btn_frame,
            text="▶️ START",
            font=("Arial", 12, "bold"),
            command=self._on_start_stop,
            width=130,
            fg_color=self.colors["accent_green"]
        )
        self.btn_start_stop.pack(side="left", padx=5)
        
        # Spacer to push buttons to right
        ctk.CTkLabel(btn_frame, text="").pack(side="left", expand=True)
        
        # Theme button at far right
        theme_icon = "🌙" if self.current_theme == "dark" else "☀️"
        self.btn_theme = ctk.CTkButton(
            btn_frame,
            text=theme_icon,
            font=("Arial", 12),
            command=self._toggle_theme,
            width=50,
            height=35,
            fg_color=self.colors["bg_secondary"],
            hover_color=self.colors["accent_purple"]
        )
        self.btn_theme.pack(side="right", padx=5)
        
        # Loot window button
        self.btn_loot_window = ctk.CTkButton(
            btn_frame,
            text="🎰 Loot Spins",
            command=self._open_loot_window,
            width=120,
            height=35,
            font=("Arial", 11, "bold"),
            fg_color=self.colors["accent_gold"]
        )
        self.btn_loot_window.pack(side="right", padx=5)
    
    def _create_general_tab(self):
        """Create General tab with master controls and log."""
        frame = self.tabs.add("General")
        
        # Master controls in General tab
        master_frame = ctk.CTkFrame(frame, fg_color=self.colors["bg_secondary"])
        master_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(
            master_frame,
            text="⚙️ MASTER CONTROLS",
            font=("Arial", 11, "bold"),
            text_color=self.colors["accent_red"]
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        chk_frame = ctk.CTkFrame(master_frame, fg_color="transparent")
        chk_frame.pack(fill="x", padx=10, pady=5)
        
        self.chk_master_battle = ctk.CTkCheckBox(
            chk_frame,
            text="Auto Battle",
            command=lambda: self.brain.set_battle_enabled(self.chk_master_battle.get())
        )
        self.chk_master_battle.pack(side="left", padx=10)
        
        self.chk_master_chests = ctk.CTkCheckBox(
            chk_frame,
            text="Auto Chests",
            command=lambda: self.brain.set_chests_enabled(self.chk_master_chests.get())
        )
        self.chk_master_chests.pack(side="left", padx=10)
        
        self.chk_master_business = ctk.CTkCheckBox(
            chk_frame,
            text="Auto Business",
            command=lambda: self._on_business_toggle()
        )
        self.chk_master_business.pack(side="left", padx=10)
        
        # Auto-refresh checkbox (default enabled)
        self.chk_auto_refresh = ctk.CTkCheckBox(
            chk_frame,
            text="Auto Refresh (1h)",
        )
        self.chk_auto_refresh.pack(side="left", padx=10)
        self.chk_auto_refresh.select()  # Default enabled
        
        # Log section
        log_frame = ctk.CTkFrame(frame, fg_color=self.colors["bg_primary"])
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Log header
        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=5, pady=(5, 0))
        
        ctk.CTkLabel(
            log_header,
            text="📋 ACTIVITY LOG",
            font=("Arial", 11, "bold"),
            text_color=self.colors["accent_blue"]
        ).pack(side="left")
        
        self.lbl_log_status = ctk.CTkLabel(
            log_header,
            text="",
            font=("Arial", 9),
            text_color=self.colors["accent_red"]
        )
        self.lbl_log_status.pack(side="left", padx=10)
        
        # Log text area
        self.log_text = ctk.CTkTextbox(
            log_frame,
            font=("Consolas", 10),
            fg_color=self.colors["bg_tertiary"],
            text_color=self.colors["text_secondary"],
            wrap="word",
            state="disabled"
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        return frame
    
    def _create_battle_tab(self):
        """Create battle tab."""
        frame = self.tabs.add("Battle")
        
        top_f = ctk.CTkFrame(frame, fg_color=self.colors["bg_primary"])
        top_f.pack(fill="x", padx=10, pady=10)
        
        self.lbl_battle_stage = ctk.CTkLabel(
            top_f, text="Stage: --", font=("Arial", 15, "bold"), text_color=self.colors["accent_gold"]
        )
        self.lbl_battle_stage.pack(side="left", padx=15)
        
        self.lbl_battle_kills = ctk.CTkLabel(top_f, text="Kills: --", font=("Arial", 13),
                                               text_color=self.colors["text_primary"])
        self.lbl_battle_kills.pack(side="left", padx=15)
        
        # NEW: Streak counter
        self.lbl_battle_streak = ctk.CTkLabel(top_f, text="Streak: --", font=("Arial", 13),
                                               text_color=self.colors["accent_orange"])
        self.lbl_battle_streak.pack(side="left", padx=15)
        
        self.chk_battle_auto = ctk.CTkCheckBox(
            top_f, text="AUTO-BATTLE", text_color=self.colors["accent_red"],
            font=("Arial", 11, "bold"),
            command=lambda: self.brain.set_battle_enabled(self.chk_battle_auto.get())
        )
        self.chk_battle_auto.pack(side="right", padx=15)
        
        # NEW: Stats frame (Attack/Defense/HP)
        stats_f = ctk.CTkFrame(frame, fg_color=self.colors["bg_secondary"])
        stats_f.pack(fill="x", padx=10, pady=5)
        
        self.lbl_battle_attack = ctk.CTkLabel(stats_f, text="ATK: --", font=("Arial", 11, "bold"),
                                                text_color=self.colors["accent_red"])
        self.lbl_battle_attack.pack(side="left", padx=15)
        
        self.lbl_battle_defense = ctk.CTkLabel(stats_f, text="DEF: --", font=("Arial", 11, "bold"),
                                               text_color=self.colors["accent_blue"])
        self.lbl_battle_defense.pack(side="left", padx=15)
        
        self.lbl_battle_hp = ctk.CTkLabel(stats_f, text="HP: --/--", font=("Arial", 11, "bold"),
                                          text_color=self.colors["accent_green"])
        self.lbl_battle_hp.pack(side="left", padx=15)
        
        # NEW: Bounty info
        self.lbl_bounty = ctk.CTkLabel(stats_f, text="", font=("Arial", 10),
                                       text_color=self.colors["text_muted"])
        self.lbl_bounty.pack(side="right", padx=15)
        
        # --- DAILY QUESTS SECTION ---
        quest_frame = ctk.CTkFrame(frame, fg_color=self.colors["bg_secondary"])
        quest_frame.pack(fill="x", padx=10, pady=5)
        
        quest_header = ctk.CTkFrame(quest_frame, fg_color="transparent")
        quest_header.pack(fill="x", padx=10, pady=(5, 0))
        
        ctk.CTkLabel(
            quest_header,
            text="🎯 Daily Quests",
            font=("Arial", 12, "bold"),
            text_color=self.colors["accent_gold"]
        ).pack(side="left")
        
        self.chk_auto_claim_quests = ctk.CTkCheckBox(
            quest_header,
            text="Auto-Claim Quest Rewards",
            text_color=self.colors["accent_green"],
            font=("Arial", 10),
            command=lambda: self.brain.settings.set("auto_claim_quests", self.chk_auto_claim_quests.get())
        )
        self.chk_auto_claim_quests.pack(side="right", padx=10)
        
        # Quests display frame
        self.quests_display_frame = ctk.CTkFrame(quest_frame, fg_color="transparent")
        self.quests_display_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_quests_status = ctk.CTkLabel(
            self.quests_display_frame,
            text="No quest data available",
            font=("Arial", 10),
            text_color=self.colors["text_muted"]
        )
        self.lbl_quests_status.pack(anchor="w")
        
        set_f = ctk.CTkFrame(frame, fg_color=self.colors["bg_secondary"])
        set_f.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(set_f, text="Flee if HP <%:", text_color=self.colors["text_primary"]).pack(side="left", padx=10)
        self.hp_limit = ctk.StringVar(value="20")
        ctk.CTkEntry(set_f, textvariable=self.hp_limit, width=50).pack(side="left")
        
        ctk.CTkLabel(set_f, text="Min Energy:", text_color=self.colors["text_primary"]).pack(side="left", padx=(20, 5))
        self.energy_limit = ctk.StringVar(value="5")
        ctk.CTkEntry(set_f, textvariable=self.energy_limit, width=50).pack(side="left")
        
        # --- SKILL PRIORITY (6 slots) ---
        skill_frame = ctk.CTkFrame(frame, fg_color=self.colors["bg_secondary"])
        skill_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            skill_frame, 
            text="⚔️ Skill Priority (6 slots):", 
            font=("Arial", 12, "bold"),
            text_color=self.colors["accent_gold"]
        ).pack(anchor="w", padx=10, pady=(5, 0))
        
        # Get detected skills from settings or use defaults
        last_skill_names = self.brain.settings.get("battle.last_skill_names", [])
        if last_skill_names:
            skills_list = list(set(last_skill_names + ["Attack", "none"]))
            skills_list.sort()
            default_skills = ["Attack"] + ["none"] * 5
        else:
            skills_list = ["Attack", "Guard", "Cry", "Power", "Dodge", "Poison", "Run", "none"]
            default_skills = ["Attack", "Guard", "Cry", "Power", "Dodge", "Poison"]
        
        self.skill_vars = {}
        slots_frame = ctk.CTkFrame(skill_frame, fg_color="transparent")
        slots_frame.pack(fill="x", padx=10, pady=5)
        
        for i in range(6):
            ctk.CTkLabel(slots_frame, text=f"{i+1}:", font=("Arial", 10, "bold")).pack(side="left", padx=(10, 2))
            var = ctk.StringVar(value=default_skills[i])
            self.skill_vars[f"slot_{i}"] = var
            dropdown = ctk.CTkOptionMenu(
                slots_frame, 
                variable=var, 
                values=skills_list, 
                width=90,
                font=("Arial", 10)
            )
            dropdown.pack(side="left", padx=(0, 8))
        
        # Update button
        def update_skill_priority():
            new_priority = []
            for i in range(6):
                skill = self.skill_vars[f"slot_{i}"].get()
                if skill and skill != "none" and skill not in new_priority:
                    new_priority.append(skill)
            # Save to settings
            self.brain.settings.set("battle.skill_priority", new_priority)
            self.add_log_entry(f"Skill priority updated: {new_priority}")
        
        ctk.CTkButton(
            slots_frame, 
            text="Update", 
            command=update_skill_priority, 
            width=70,
            font=("Arial", 10, "bold")
        ).pack(side="left", padx=10)
        
        return frame
    
    def _create_chests_tab(self):
        """Create chests tab."""
        frame = self.tabs.add("Chests")
        
        top_f = ctk.CTkFrame(frame, fg_color=self.colors["bg_primary"])
        top_f.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            top_f, text="🎁 CHEST SUMMONING",
            font=("Arial", 15, "bold"), text_color=self.colors["accent_gold"]
        ).pack(side="left", padx=15)
        
        # NEW: Show bronze wallet
        self.lbl_chest_bronze = ctk.CTkLabel(top_f, text="Bronze: --", font=("Arial", 12, "bold"),
                                              text_color=self.colors["accent_gold"])
        self.lbl_chest_bronze.pack(side="left", padx=20)
        
        self.chk_chests_auto = ctk.CTkCheckBox(
            top_f, text="AUTO-SUMMON", text_color=self.colors["accent_green"],
            font=("Arial", 11, "bold"),
            command=lambda: self.brain.set_chests_enabled(self.chk_chests_auto.get())
        )
        self.chk_chests_auto.pack(side="right", padx=15)
        
        safe_f = ctk.CTkFrame(frame)
        safe_f.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(safe_f, text="Stop if Bronze <", text_color=self.colors["text_primary"]).pack(side="left", padx=10)
        self.chest_limit = ctk.StringVar(value="0")
        ctk.CTkEntry(safe_f, textvariable=self.chest_limit, width=80).pack(side="left")
        
        # Chest categories split into two columns
        grid_f = ctk.CTkFrame(frame, fg_color="transparent")
        grid_f.pack(fill="both", expand=True, padx=10, pady=10)
        
        # RESOURCES column
        res_f = ctk.CTkScrollableFrame(grid_f, label_text="RESOURCES", label_font=("Arial", 12, "bold"),
                                        fg_color=self.colors["bg_secondary"])
        res_f.pack(side="left", fill="both", expand=True, padx=5)
        
        # ARMORY column
        arm_f = ctk.CTkScrollableFrame(grid_f, label_text="ARMORY", label_font=("Arial", 12, "bold"),
                                        fg_color=self.colors["bg_secondary"])
        arm_f.pack(side="left", fill="both", expand=True, padx=5)
        
        # Store chest row widgets for updating
        self.chest_rows = {}
        self.chest_data = {
            "Resource": ["Wood Chest", "Bronze Chest", "Silver Chest", "Gold Chest",
                        "Diamond Chest", "Ruby Chest", "Emerald Chest"],
            "Armory": ["Wood Armory", "Bronze Armory", "Silver Armory", "Gold Armory",
                       "Diamond Armory", "Ruby Armory", "Emerald Armory"]
        }
        
        # Load saved chest selections
        saved_selections = self.brain.settings.get("chests.selected", {"Resource": [], "Armory": []})
        
        for cat, names in self.chest_data.items():
            parent_frame = res_f if cat == "Resource" else arm_f
            for name in names:
                row = ctk.CTkFrame(parent_frame, fg_color="transparent")
                row.pack(fill="x", pady=5, padx=5)
                
                # Checkbox for selection - load saved state
                is_selected = name in saved_selections.get(cat, [])
                var = ctk.BooleanVar(value=is_selected)
                cb = ctk.CTkCheckBox(row, text=name, variable=var, font=("Arial", 11))
                cb.pack(side="left", fill="x", expand=True)
                
                # Sync on every click
                cb.configure(command=lambda n=name: self._on_chest_clicked(n))
                
                # Cost label
                cost_lbl = ctk.CTkLabel(row, text="--", font=("Arial", 10), 
                                        text_color=self.colors["text_muted"], width=60)
                cost_lbl.pack(side="left", padx=5)
                
                # Status label
                status_lbl = ctk.CTkLabel(row, text="Unknown", font=("Arial", 10),
                                          text_color=self.colors["text_muted"], width=80)
                status_lbl.pack(side="left", padx=5)
                
                self.chest_rows[name] = {
                    'var': var,
                    'checkbox': cb,
                    'cost_label': cost_lbl,
                    'status_label': status_lbl
                }
        
        return frame
    
    def _create_business_tab(self):
        """Create business tab."""
        frame = self.tabs.add("Business")
        
        brz_f = ctk.CTkFrame(frame, fg_color=self.colors["bg_secondary"], border_width=1,
                            border_color=self.colors["border_color"])
        brz_f.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(brz_f, text="STORED BRONZE", font=("Arial", 10, "bold"),
                     text_color=self.colors["text_primary"]).pack(pady=(5, 0))
        self.lbl_stored_bronze = ctk.CTkLabel(
            brz_f, text="0", font=("Arial", 20, "bold"), text_color=self.colors["accent_gold"]
        )
        self.lbl_stored_bronze.pack(pady=(0, 0))
        
        self.brz_prog = ctk.CTkProgressBar(
            brz_f, width=350, height=14,
            progress_color=self.colors["accent_gold"], fg_color=self.colors["bg_primary"],
            border_width=2, border_color=self.colors["accent_gold"]
        )
        self.brz_prog.pack(pady=(0, 5), padx=12, fill="x")
        self.brz_prog.set(0)
        
        mat_f = ctk.CTkFrame(frame, fg_color=self.colors["bg_secondary"], border_width=1,
                            border_color=self.colors["border_color"])
        mat_f.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(mat_f, text="STORED MATERIALS", font=("Arial", 10, "bold"),
                     text_color=self.colors["text_primary"]).pack(pady=(5, 0))
        
        self.mat_prog_bars = {}
        mat_names = ["Wood", "Wheat", "Rock", "Food", "Cloth"]
        for m in mat_names:
            row = ctk.CTkFrame(mat_f, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=1)
            ctk.CTkLabel(row, text=m, width=50, anchor="w", font=("Arial", 11, "bold"),
                        text_color=self.colors["text_primary"]).pack(side="left")
            lbl = ctk.CTkLabel(row, text="--", font=("Arial", 11, "bold"),
                               text_color=self.colors["accent_gold"])
            lbl.pack(side="left", padx=(4, 8))
            pb = ctk.CTkProgressBar(row, height=10, progress_color=self.colors["accent_blue"],
                                    fg_color=self.colors["bg_primary"])
            pb.pack(side="right", fill="x", expand=True, padx=(0, 4))
            pb.set(0)
            self.mat_prog_bars[m] = (lbl, pb)
        
        auto_f = ctk.CTkFrame(frame, fg_color=self.colors["bg_primary"])
        auto_f.pack(fill="x", padx=10, pady=(10, 5))
        
        row_b = ctk.CTkFrame(auto_f, fg_color="transparent")
        row_b.pack(fill="x", pady=3)
        self.chk_auto_collect = ctk.CTkCheckBox(
            row_b, text="Auto Collect All",
            command=lambda: self.brain.set_business_auto_collect(self.chk_auto_collect.get()),
            text_color=self.colors["text_primary"]
        )
        self.chk_auto_collect.pack(side="left", padx=6)
        ctk.CTkLabel(row_b, text="Every (min):", text_color=self.colors["text_primary"]).pack(side="left", padx=(10, 4))
        self.var_collect_min = ctk.StringVar(value="30")
        entry_collect = ctk.CTkEntry(row_b, textvariable=self.var_collect_min, width=40)
        entry_collect.pack(side="left")
        entry_collect.bind('<Return>', lambda e: self._on_collect_interval_change())
        entry_collect.bind('<FocusOut>', lambda e: self._on_collect_interval_change())
        self.lbl_collect_cd = ctk.CTkLabel(row_b, text="off", font=("Arial", 10, "bold"),
                                          text_color=self.colors["accent_orange"])
        self.lbl_collect_cd.pack(side="right", padx=4)
        
        return frame
    
    def _create_status_bar(self):
        """Create status bar at bottom."""
        self.status_frame = ctk.CTkFrame(self, fg_color=self.colors["bg_primary"], height=25)
        self.status_frame.pack(fill="x", padx=15, pady=(0, 10))
        self.status_frame.pack_propagate(False)
        
        self.lbl_creator = ctk.CTkLabel(
            self.status_frame,
            text=f"Created by {CREATOR_NAME}",
            font=("Arial", 10),
            text_color=self.colors["accent_gold"]
        )
        self.lbl_creator.pack(side="left", padx=10)
        
        # Mode switcher in the middle
        mode_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        mode_frame.pack(side="left", expand=True)
        
        self.lbl_mode = ctk.CTkLabel(
            mode_frame,
            text="MODE: IDLE",
            font=("Arial", 10, "bold"),
            text_color=self.colors["text_muted"]
        )
        self.lbl_mode.pack()
        
        self.lbl_status = ctk.CTkLabel(
            self.status_frame,
            text="Disconnected",
            font=("Arial", 10),
            text_color=self.colors["accent_red"]
        )
        self.lbl_status.pack(side="right", padx=10)
    
    def _toggle_theme(self):
        """Toggle between light and dark themes."""
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.current_theme = new_theme
        self.colors = self.THEMES[new_theme]
        
        # Save theme preference
        self.brain.settings.set("general.theme", new_theme)
        
        # Apply theme to customtkinter
        ctk.set_appearance_mode(new_theme)
        
        # Update theme button icon
        theme_icon = "🌙" if new_theme == "dark" else "☀️"
        self.btn_theme.configure(
            text=theme_icon,
            fg_color=self.colors["bg_secondary"],
            hover_color=self.colors["accent_purple"]
        )
        
        # Recreate UI components with new theme colors
        self._apply_theme_to_ui()
        
        self.add_log_entry(f"Theme changed to {new_theme} mode")
    
    def _apply_theme_to_ui(self):
        """Apply theme colors to all UI components."""
        c = self.colors
        
        # Info bar
        self.info_frame.configure(fg_color=c["bg_primary"])
        self.lbl_user.configure(text_color=c["accent_gold"])
        self.lbl_class.configure(text_color=c["text_muted"])
        self.lbl_level.configure(text_color=c["accent_blue"])
        self.xp_bar.configure(progress_color=c["accent_gold"], fg_color=c["progress_bg"])
        self.lbl_xp.configure(text_color=c["text_muted"])
        self.lbl_energy_txt.configure(text_color=c["accent_cyan"])
        self.energy_bar.configure(progress_color=c["accent_cyan"], fg_color=c["progress_bg"])
        self.lbl_bronze.configure(text_color=c["accent_gold"])
        self.lbl_tlrpg.configure(text_color=c["accent_cyan"])
        self.lbl_tlrpg_eur.configure(text_color=c["text_muted"])
        self.lbl_eur.configure(text_color=c["accent_green"])
        
        # Materials bar
        self.mat_frame.configure(fg_color=c["bg_secondary"])
        for lbl in self.mat_labels.values():
            lbl.configure(text_color=c["accent_gold"])
        for lbl in self.rare_labels.values():
            lbl.configure(text_color=c["accent_gold"])
        
        # Status bar
        self.status_frame.configure(fg_color=c["bg_primary"])
        self.lbl_creator.configure(text_color=c["accent_gold"])
        self.lbl_mode.configure(text_color=c["text_muted"])
        self.lbl_status.configure(text_color=c["accent_red"])
        
        # Update tabs by reconfiguring tabview
        self.tabs.configure(segmented_button_selected_color=c["tab_selected"])
    
    def _toggle_log(self):
        """Toggle log recording on/off."""
        if self.log_running:
            self.log_running = False
            if self.log_file:
                self.log_file.close()
                self.log_file = None
            self.lbl_log_status.configure(text="", text_color=self.colors["accent_red"])
            self.add_log_entry("Log recording stopped")
        else:
            self.log_running = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bot_log_{timestamp}.txt"
            try:
                self.log_file = open(filename, "w", encoding="utf-8")
                self.log_file.write(f"TokenLords Bot Log - Started {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                self.log_file.write(f"Created by {CREATOR_NAME}\n")
                self.log_file.write("=" * 50 + "\n\n")
                self.lbl_log_status.configure(text=f"● Recording", text_color=self.colors["accent_green"])
                self.add_log_entry(f"Log recording started: {filename}")
            except Exception as e:
                self.add_log_entry(f"Failed to start log: {e}")
                self.log_running = False
    
    def _save_log(self):
        """Save current log content to a file."""
        try:
            # Get current log content
            self.log_text.configure(state="normal")
            log_content = self.log_text.get("1.0", "end-1c")
            self.log_text.configure(state="disabled")
            
            if not log_content.strip():
                self.add_log_entry("No log content to save")
                return
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bot_log_saved_{timestamp}.txt"
            
            # Write to file
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"TokenLords Bot Log - Saved {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Created by {CREATOR_NAME}\n")
                f.write("=" * 50 + "\n\n")
                f.write(log_content)
            
            self.add_log_entry(f"Log saved to: {filename}")
        except Exception as e:
            self.add_log_entry(f"Failed to save log: {e}")
    
    def add_log_entry(self, message: str):
        """Add entry to log queue (thread-safe)."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"[{timestamp}] {message}")
    
    def _process_command_queue(self):
        """Process commands from brain queue in main thread (Playwright-safe)."""
        try:
            while not self.command_queue.empty():
                command = self.command_queue.get_nowait()
                cmd_type = command.get("type")
                
                if cmd_type == "update_state":
                    # Update state from current page
                    if self.brain.browser.page:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.brain.state.update_from_page(self.brain.browser.page))
                        loop.close()
                
                elif cmd_type == "navigate":
                    # Navigate to URL
                    url = command.get("url")
                    if self.brain.browser.page:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.brain.browser.navigate(url))
                        loop.close()
                
                elif cmd_type == "click":
                    # Click element
                    selector = command.get("selector")
                    if self.brain.browser.page:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.brain.browser.page.locator(selector).first.click())
                        loop.close()
                
                elif cmd_type == "get_text":
                    # Get text from element
                    selector = command.get("selector")
                    result = None
                    if self.brain.browser.page:
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(self.brain.browser.page.inner_text(selector))
                        loop.close()
                    self.result_queue.put(result)
        except Exception as e:
            print(f"[UI] Command queue error: {e}")
        
        # Schedule next queue processing
        self.after(100, self._process_command_queue)

    def _on_hook(self):
        """Handle hook button click - connect and load initial data."""
        import urllib.request
        try:
            # Check if Edge debugger is available
            urllib.request.urlopen("http://localhost:9222/json/version", timeout=2)
        except:
            self.add_log_entry("Browser not found on port 9222 - Click LAUNCH first")
            return
        
        # Connect and load all data in background thread
        def do_hook():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def hook_async():
                self.add_log_entry("Connecting to browser and loading data...")
                result = await self.brain.connect()
                if result:
                    # Update UI from thread (brain.connect already loads initial state)
                    self.after(0, lambda: self.btn_hook.configure(text="🔗 CONNECTED", fg_color=self.colors["accent_green"]))
                    self.after(0, lambda: self.lbl_status.configure(text="Connected - Data Loaded", text_color=self.colors["accent_green"]))
                    self.after(0, self._update_ui)
                    self.add_log_entry("Connected! All data loaded from page.")
                else:
                    self.add_log_entry("Failed to connect to browser")
            
            loop.run_until_complete(hook_async())
        
        import threading
        threading.Thread(target=do_hook, daemon=True).start()
    
    def _launch_browser(self):
        """Launch Edge browser with remote debugging."""
        import subprocess
        import os
        import shutil
        
        # Possible Edge paths to try
        edge_paths = [
            # System-wide installs
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            # User profile installs
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            # Try to find in PATH
            shutil.which("msedge"),
            shutil.which("msedge.exe"),
        ]
        
        # Find first existing Edge executable
        edge_exe = None
        for path in edge_paths:
            if path and os.path.exists(path):
                edge_exe = path
                break
        
        if not edge_exe:
            self.add_log_entry("Microsoft Edge not found. Please install Edge or add it to PATH.")
            return
        
        # Use current working directory for automation profile
        user_data_dir = os.path.join(os.getcwd(), "automation_profile")
        
        try:
            subprocess.Popen([
                edge_exe,
                "--remote-debugging-port=9222",
                f"--user-data-dir={user_data_dir}",
                "https://game.tokenlordsrpg.com/"
            ])
            self.add_log_entry(f"Launched Edge browser from: {edge_exe}")
        except Exception as e:
            self.add_log_entry(f"Failed to launch browser: {e}")
    
    def _sync_chest_selections(self):
        """Sync chest UI checkbox selections to settings."""
        selected = {"Resource": [], "Armory": []}
        for cat, names in self.chest_data.items():
            for name in names:
                if self.chest_rows[name]['var'].get():
                    selected[cat].append(name)
        self.brain.settings.set("chests.selected", selected)
        print(f"[UI] Chest selections synced: {selected}")
    
    def _on_chest_clicked(self, name):
        """Handle chest checkbox click - sync immediately."""
        self._sync_chest_selections()
    
    def _on_start_stop(self):
        """Toggle bot start/stop."""
        if self.brain.is_running:
            self.brain.stop()
            self.btn_start_stop.configure(text="▶️ START", fg_color=self.colors["accent_green"])
            self.add_log_entry("Bot stopped")
        else:
            # Sync settings before starting
            self._sync_chest_selections()
            self.brain.is_running = True
            self.btn_start_stop.configure(text="⏸️ STOP", fg_color=self.colors["accent_red"])
            self.add_log_entry("Bot started")
            # Start the brain's main loop in a separate thread
            import threading
            self._brain_thread = threading.Thread(target=self._run_brain_thread, daemon=True)
            self._brain_thread.start()
    
    def _run_brain_thread(self):
        """Run brain loop in a separate thread with its own event loop."""
        asyncio.run(self._brain_loop())
    
    async def _brain_loop(self):
        """Run the brain's main loop - connect and run all in same thread."""
        # Connect in brain thread (ensures same thread for all Playwright ops)
        print("[UI] Brain thread connecting to browser...")
        result = await self.brain.connect()
        if result:
            # Update UI from brain thread via after()
            self.after(0, lambda: self.btn_hook.configure(text="🔗 CONNECTED", fg_color=self.colors["accent_green"]))
            self.after(0, lambda: self.lbl_status.configure(text="Running", text_color=self.colors["accent_green"]))
            self.add_log_entry("Brain connected - starting automation")
        else:
            self.add_log_entry("Failed to connect - make sure browser is running on port 9222")
            self.brain.is_running = False
            return
        
        # Main loop - all Playwright operations in this thread
        while self.brain.is_running:
            try:
                await self.brain.tick()
            except Exception as e:
                print(f"[UI] Brain tick error: {e}")
            await asyncio.sleep(0.5)
    
    def _update_business_countdowns_callback(self, data):
        """Callback for business countdown updates from brain."""
        try:
            collect_cd = data.get("collect_countdown", None)
            auto_collect = data.get("auto_collect", False)
            
            # Update Collect All countdown label
            if auto_collect and collect_cd is not None and collect_cd >= 0:
                if collect_cd > 0:
                    minutes = collect_cd // 60
                    seconds = collect_cd % 60
                    self.lbl_collect_cd.configure(text=f"{minutes:02d}:{seconds:02d}", text_color="#27ae60")
                else:
                    self.lbl_collect_cd.configure(text="READY", text_color="#e67e22")
            else:
                self.lbl_collect_cd.configure(text="off", text_color="gray")
        except Exception as e:
            print(f"[UI] Error updating business countdowns: {e}")
    
    def _on_business_toggle(self):
        """Handle business enable/disable."""
        enabled = self.chk_master_business.get()
        print(f"[UI] Business master toggle: {enabled}")
        self.brain.set_business_enabled(enabled)
        if enabled:
            self.chk_auto_collect.select()
            self.brain.set_business_auto_collect(True)
            self.add_log_entry("Business automation enabled")
        else:
            self.chk_auto_collect.deselect()
            self.brain.set_business_auto_collect(False)
            self.add_log_entry("Business automation disabled")
    
    def _on_collect_interval_change(self):
        """Handle Collect All interval change - temporary setting only."""
        try:
            minutes = int(self.var_collect_min.get())
            if minutes < 1:
                minutes = 1
                self.var_collect_min.set("1")
            self.brain.set_business_collect_interval(minutes)
        except ValueError:
            self.var_collect_min.set("30")
            self.brain.set_business_collect_interval(30)
    
    async def _run_brain_loop(self):
        """Run the brain's main loop."""
        while self.brain.is_running:
            try:
                await self.brain.tick()
            except Exception as e:
                print(f"[UI] Brain tick error: {e}")
            await asyncio.sleep(0.5)
    
    def _on_log_toggle(self):
        """Handle log enabled checkbox toggle."""
        enabled = self.chk_log_enabled.get()
        if enabled and not self.log_running:
            # Auto-start logging when checkbox is checked
            self._toggle_log()
        elif not enabled and self.log_running:
            # Stop logging when checkbox is unchecked
            self._toggle_log()
    
    def _open_loot_window(self):
        """Open the loot chest spins window."""
        from loot_window import LootWindow
        LootWindow.open_window(self, self.brain, self)
        self.add_log_entry("Loot window opened")
    
    def _on_state_update(self, state):
        """Callback when brain updates state - triggers UI refresh."""
        # Check for skill reset notification
        if isinstance(state, dict) and state.get("skill_reset"):
            new_priority = state.get("new_priority", [])
            self.add_log_entry(f"⚠️ Skills reset to: {new_priority}")
            # Reload settings to update UI dropdowns
            self._load_settings_into_ui()
        
        # UI will be updated on next _update_ui tick (1 second interval)
        pass
    
    def _update_ui(self):
        """Update UI with current game state."""
        status = self.brain.get_status()
        
        # Info bar
        player = status.get("player", {})
        self.lbl_user.configure(text=player.get("name", "Not Connected"))
        self.lbl_class.configure(text=player.get("class", ""))
        self.lbl_level.configure(text=f"LV: {player.get('level', '--')}")
        
        # Weekly payout
        weekly_current = player.get('weekly_energy_current', 0)
        weekly_required = player.get('weekly_energy_required', 0)
        if weekly_required > 0:
            self.lbl_weekly.configure(text=f"Weekly: {weekly_current}/{weekly_required}")
        else:
            self.lbl_weekly.configure(text="Weekly: --/--")
        
        # XP - read from player dict
        xp = player.get("xp", "")
        xp_progress = player.get("xp_progress", 0)
        if isinstance(xp, str) and xp:
            self.lbl_xp.configure(text=xp)
            self.xp_bar.set(xp_progress)
        else:
            self.lbl_xp.configure(text="--/--")
            self.xp_bar.set(0)
        
        energy = status.get("energy", {})
        energy_current = energy.get("current", 0)
        energy_max = energy.get("max", 0)
        self.lbl_energy_txt.configure(text=f"{energy_current:.1f} / {energy_max:.0f}")
        self.energy_bar.set(energy.get("progress", 0))
        
        # Currencies
        currency = status.get("currency", {})
        self.lbl_bronze.configure(text=f"{currency.get('bronze', 0):,}")
        self.lbl_tlrpg.configure(text=f"${currency.get('tlrpg', 0):.2f}")
        tlrpg_eur = currency.get('tlrpg_eur', '')
        # Remove € if already present to avoid duplication
        if tlrpg_eur:
            tlrpg_eur = tlrpg_eur.replace('€', '').strip()
            self.lbl_tlrpg_eur.configure(text=f"€{tlrpg_eur}")
        else:
            self.lbl_tlrpg_eur.configure(text="")
        # Remove € if already present to avoid duplication
        balance = str(currency.get('balance', 0)).replace('€', '').strip()
        self.lbl_eur.configure(text=f"€{balance}")
        
        # Materials bar
        materials = status.get("materials", {})
        for name, lbl in self.mat_labels.items():
            val = materials.get(name, "--")
            lbl.configure(text=val)
        
        for name, lbl in self.rare_labels.items():
            val = materials.get(name, "--")
            lbl.configure(text=val)
        
        # Battle tab - Enhanced with new data
        battle = status.get("battle", {})
        self.lbl_battle_stage.configure(text=f"Stage: {battle.get('stage', '--')}")
        self.lbl_battle_kills.configure(text=f"Kills: {battle.get('kills', '--')}")
        
        # NEW: Update streak
        streak = battle.get('streak', 0)
        if streak > 0:
            self.lbl_battle_streak.configure(text=f"Streak: {streak}")
        else:
            self.lbl_battle_streak.configure(text="Streak: --")
        
        # NEW: Update stats
        attack = battle.get('attack', 0)
        defense = battle.get('defense', 0)
        self.lbl_battle_attack.configure(text=f"ATK: {attack:,}" if attack > 0 else "ATK: --")
        self.lbl_battle_defense.configure(text=f"DEF: {defense:,}" if defense > 0 else "DEF: --")
        
        # NEW: Update HP from player stats
        player_stats = status.get("player", {})
        hp_current = player_stats.get('hp_current', 0)
        hp_max = player_stats.get('hp_max', 0)
        if hp_max > 0:
            self.lbl_battle_hp.configure(text=f"HP: {hp_current}/{hp_max}")
        else:
            self.lbl_battle_hp.configure(text="HP: --/--")
        
        # NEW: Update bounty info
        bounty_target = battle.get('bounty_target', '')
        bounty_reward = battle.get('bounty_reward', '')
        if bounty_target:
            bounty_text = f"🎯 Bounty: {bounty_target}"
            if bounty_reward:
                bounty_text += f" ({bounty_reward})"
            self.lbl_bounty.configure(text=bounty_text)
        else:
            self.lbl_bounty.configure(text="")
        
        # NEW: Update quests display
        quests = status.get("quests", [])
        if quests:
            quest_lines = []
            for q in quests:
                name = q.get('name', 'Unknown')
                quest_status = q.get('status', 'in_progress')
                progress = q.get('progress_pct', 0)
                reward = q.get('reward', '')
                
                if quest_status == "claimable":
                    quest_lines.append(f"✅ {name} - Ready to claim!")
                elif quest_status == "completed":
                    quest_lines.append(f"✓ {name} - Done")
                else:
                    desc = q.get('description', f'{progress}%')
                    quest_lines.append(f"⏳ {name} - {desc}")
            
            quest_text = " | ".join(quest_lines)
            self.lbl_quests_status.configure(text=quest_text, text_color=self.colors["text_primary"])
        else:
            self.lbl_quests_status.configure(text="No quest data available", text_color=self.colors["text_muted"])
        
        # NEW: Update chests tab with real data
        chests = status.get("chests", {})
        self.lbl_chest_bronze.configure(text=f"Bronze: {chests.get('bronze', 0):,}")
        
        available_chests = chests.get('available_chests', [])
        for chest_data in available_chests:
            name = chest_data.get('name', '')
            if name in self.chest_rows:
                row = self.chest_rows[name]
                # Update cost
                cost = chest_data.get('cost', 0)
                row['cost_label'].configure(text=f"{cost:,}" if cost > 0 else "--")
                # Update status/cooldown
                cooldown = chest_data.get('cooldown', '')
                can_summon = chest_data.get('can_summon', False)
                if cooldown and cooldown != "Ready":
                    row['status_label'].configure(text=cooldown, text_color=self.colors["accent_red"])
                elif can_summon:
                    row['status_label'].configure(text="Ready", text_color=self.colors["accent_green"])
                else:
                    row['status_label'].configure(text="Locked", text_color=self.colors["text_muted"])
        
        # Business tab
        business = status.get("business", {})
        self.lbl_stored_bronze.configure(text=f"{business.get('stored_bronze', 0):,}")
        self.brz_prog.set(business.get("bronze_progress", 0))
        
        stored_mats = business.get("stored_materials", {})
        for mat, (lbl, pb) in self.mat_prog_bars.items():
            val = stored_mats.get(mat, (0, 0))
            lbl.configure(text=f"{val[0]:,}")
            if val[1] > 0:
                pb.set(min(1.0, val[0] / val[1]))
        
        # Countdown label - format raw seconds to MM:SS
        collect_cd = business.get("collect_countdown", -1)
        if collect_cd >= 0:
            minutes = collect_cd // 60
            seconds = collect_cd % 60
            self.lbl_collect_cd.configure(text=f"{minutes:02d}:{seconds:02d}")
        else:
            self.lbl_collect_cd.configure(text="off")
        
        # Update mode display based on active features
        modes = []
        if self.brain.is_running:
            if self.brain.settings.battle_enabled:
                modes.append("BATTLE")
            if self.brain.settings.chests_enabled:
                modes.append("CHESTS")
            if self.brain.settings.business_enabled:
                modes.append("BUSINESS")
        
        if modes:
            mode_text = f"MODE: {' + '.join(modes)}"
            mode_color = self.colors["accent_green"]
        else:
            mode_text = "MODE: IDLE"
            mode_color = self.colors["text_muted"]
        
        self.lbl_mode.configure(text=mode_text, text_color=mode_color)
        
        # Schedule next update
        self.after(1000, self._update_ui)
