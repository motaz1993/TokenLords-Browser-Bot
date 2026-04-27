"""Loot Chest Spins Window - Automated loot chest opening from battle page."""
import customtkinter as ctk
from datetime import datetime


class LootWindow(ctk.CTkToplevel):
    """Window for automated loot chest spins from battle page."""
    
    # Class variable for persistent reward log
    reward_log = []
    
    # Class variable to track if window is already open
    instance = None
    
    @classmethod
    def open_window(cls, master, brain, ui):
        """Open loot window if not already open, otherwise focus existing window."""
        if cls.instance is not None and cls.instance.winfo_exists():
            cls.instance.lift()
            cls.instance.focus()
            return
        cls.instance = cls(master, brain, ui)
    
    def __init__(self, master, brain, ui, **kwargs):
        super().__init__(master, **kwargs)
        self.brain = brain
        self.ui = ui
        self.title("Loot Chest Spins")
        self.geometry("700x600")
        
        # Make window modal - grab focus and block parent
        self.transient(master)
        self.grab_set()
        
        # State variables
        self.is_running = False
        self.spins_count = 0
        self.check_interval = None
        self.opening_interval = None
        self.brain_was_running = False  # Track if brain was already running
        
        self._create_ui()
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Check if brain is running, if not start it via UI
        if self.brain:
            self.brain_was_running = self.brain.is_running
            if not self.brain.is_running:
                print("[LootWindow] Brain not running, starting via UI...")
                self.ui._on_start_stop()
            
            # Set brain to loot mode
            self.brain.loot_mode = True
        
        # Request navigation after 2 seconds
        self.after(2000, self._request_navigation)
        
        # Start polling for results
        self._start_polling()
    
    def _create_ui(self):
        """Create the loot window UI."""
        # Main frame
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(
            main_frame,
            text="🎰 Loot Chest Spins",
            font=("Arial", 20, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        # Spins display frame
        spins_frame = ctk.CTkFrame(main_frame)
        spins_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(
            spins_frame,
            text="Available Spins:",
            font=("Arial", 12)
        ).pack(side="left", padx=10)
        
        self.lbl_spins = ctk.CTkLabel(
            spins_frame,
            text="--",
            font=("Arial", 16, "bold"),
            text_color="#e67e22"
        )
        self.lbl_spins.pack(side="left", padx=10)
        
        # Status display
        self.lbl_status = ctk.CTkLabel(
            main_frame,
            text="Idle",
            font=("Arial", 12),
            text_color="gray"
        )
        self.lbl_status.pack(pady=(0, 10))
        
        # Control buttons frame
        control_frame = ctk.CTkFrame(main_frame)
        control_frame.pack(fill="x", pady=(0, 15))
        
        self.btn_start_stop = ctk.CTkButton(
            control_frame,
            text="▶️ Start Opening",
            command=self._toggle_opening,
            width=150,
            height=40,
            font=("Arial", 12, "bold"),
            fg_color="#27ae60",
            state="disabled"
        )
        self.btn_start_stop.pack(side="left", padx=10)
        
        self.btn_clear_log = ctk.CTkButton(
            control_frame,
            text="🗑️ Clear Log",
            command=self._clear_log,
            width=120,
            height=40,
            font=("Arial", 11, "bold"),
            fg_color="#c0392b"
        )
        self.btn_clear_log.pack(side="right", padx=10)
        
        # Log display
        log_label = ctk.CTkLabel(
            main_frame,
            text="📋 Reward Log",
            font=("Arial", 12, "bold")
        )
        log_label.pack(anchor="w", pady=(0, 5))
        
        self.log_text = ctk.CTkTextbox(
            main_frame,
            font=("Consolas", 10),
            fg_color="#1a1a1a",
            text_color="#ffffff",
            wrap="word",
            height=20
        )
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Load existing log
        self._load_log()
    
    def _request_navigation(self):
        """Request the brain to navigate to battle page."""
        if self.brain:
            self.brain.request_loot_navigation()
            self.lbl_status.configure(text="Navigating to battle page...", text_color="#f39c12")
            self._add_log_entry("Requested navigation to battle page...")
    
    def _start_polling(self):
        """Poll brain for loot results."""
        self.check_interval = self.after(500, self._check_results)
    
    def _check_results(self):
        """Check if brain has completed navigation and read spins."""
        if not self.brain:
            return
        
        # Check if result is available
        if self.brain.loot_spins_count is not None:
            if self.brain.loot_spins_count == -1:
                # Error occurred
                error = self.brain.loot_spins_error or "Unknown error"
                self.lbl_status.configure(text=f"Error: {error}", text_color="#e74c3c")
                self._add_log_entry(f"Error reading spins: {error}")
            else:
                # Success - update spins from page
                self.spins_count = self.brain.loot_spins_count
                self.lbl_spins.configure(text=str(self.spins_count))
                self.lbl_status.configure(text="Ready", text_color="#27ae60")
                self._add_log_entry(f"Spins loaded: {self.spins_count}")
                
                # Enable Start button
                self.btn_start_stop.configure(state="normal")
                
                # Start continuous spins counter polling
                self._start_spins_polling()
            
            # Stop initial polling
            return
        
        # Continue polling
        self.check_interval = self.after(500, self._check_results)
    
    def _start_spins_polling(self):
        """Start continuous polling of spins counter from page."""
        self.check_interval = self.after(500, self._poll_spins_counter)
    
    def _poll_spins_counter(self):
        """Poll brain to read current spins counter from page."""
        if self.brain and self.brain.loot_mode:
            self.brain.loot_read_spins_requested = True
        
        # Update UI with current value
        if self.brain and self.brain.loot_spins_count is not None:
            self.spins_count = self.brain.loot_spins_count
            self.lbl_spins.configure(text=str(self.spins_count))
        
        # Continue polling
        self.check_interval = self.after(500, self._poll_spins_counter)
    
    def _toggle_opening(self):
        """Toggle opening loop on/off."""
        if self.is_running:
            self._stop_opening()
        else:
            self._start_opening()
    
    def _start_opening(self):
        """Start the automated opening loop."""
        if self.spins_count == 0:
            self._add_log_entry("No spins available - navigate to battle page first")
            return
        
        self.is_running = True
        self.btn_start_stop.configure(text="⏹️ Stop Opening", fg_color="#e74c3c")
        self.lbl_status.configure(text="Opening chests...", text_color="#27ae60")
        
        # Start the opening loop (polling pattern)
        self._start_opening_loop()
    
    def _stop_opening(self):
        """Stop the automated opening loop."""
        self.is_running = False
        if self.opening_interval:
            self.after_cancel(self.opening_interval)
            self.opening_interval = None
        self.btn_start_stop.configure(text="▶️ Start Opening", fg_color="#27ae60")
        self.lbl_status.configure(text="Stopped", text_color="#e67e22")
    
    def _start_opening_loop(self):
        """Start the opening loop using polling pattern."""
        if self.is_running and self.spins_count > 0:
            # Request brain to open a chest
            if self.brain:
                self.brain.request_loot_open()
            
            # Check result after delay
            self.opening_interval = self.after(1000, self._check_opening_result)
        else:
            if self.spins_count == 0:
                self._add_log_entry("No more spins available")
            self._stop_opening()
    
    def _check_opening_result(self):
        """Check if brain completed opening and update spins."""
        # Check if brain parsed rewards from live feed
        rewards = self.brain.loot_rewards_feed if self.brain else []
        
        # Don't decrement spins locally - counter is read from page
        
        # Add log entries from live feed (show recent drops with player names)
        timestamp = datetime.now().strftime("%H:%M:%S")
        if rewards:
            # Show top 3 most recent rewards
            for i, r in enumerate(rewards[:3]):
                log_entry = f"[{timestamp}] {r['player']}: {r['reward']} {r['tier']} x{r['amount']}"
                self._add_log_entry(log_entry)
                LootWindow.reward_log.append(log_entry)
        else:
            log_entry = f"[{timestamp}] Chest opened (no reward data)"
            self._add_log_entry(log_entry)
            LootWindow.reward_log.append(log_entry)
        
        # Continue loop
        self._start_opening_loop()
    
    def _add_log_entry(self, entry):
        """Add entry to log display."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", entry + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def _load_log(self):
        """Load persistent log into display."""
        self.log_text.configure(state="normal")
        for entry in LootWindow.reward_log:
            self.log_text.insert("end", entry + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
    
    def _clear_log(self):
        """Clear the persistent log."""
        LootWindow.reward_log.clear()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
    
    
    def _on_close(self):
        """Handle window close - stop opening, exit loot mode, keep log."""
        self._stop_opening()
        if self.check_interval:
            self.after_cancel(self.check_interval)
        
        # Exit loot mode
        if self.brain:
            self.brain.loot_mode = False
            self.brain.loot_stop_requested = True
            
            # Stop brain loop if we started it
            if not self.brain_was_running:
                print("[LootWindow] Stopping brain loop (we started it)")
                self.ui._on_start_stop()
        
        LootWindow.instance = None
        self.destroy()
