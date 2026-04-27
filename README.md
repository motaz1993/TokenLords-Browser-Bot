# TokenLords Browser Bot

State-driven browser automation bot for TokenLords RPG built with Python, Playwright, and CustomTkinter.

This project automates a continuous gameplay loop using rule-based decision logic, live game-state monitoring, prioritized task execution, and recovery handling.

Rather than functioning as a simple click macro, the bot acts as a modular automation agent capable of managing combat, chest decisions, timed business tasks, reward collection, and interrupt-driven events.

---

## Core Features

### Automated Battle Engine
- Detects battle availability
- Starts and manages combat cycles
- Executes skill usage based on priority logic
- Monitors battle states continuously

### Dynamic Chest Automation
- Opens chests automatically
- Selects chest types using decision rules
- Tracks previous selections to support adaptive chest handling
- Includes separate loot spin handling window

### Business / Resource Collection
- Monitors business timers
- Collects available resources automatically
- Returns to main automation flow after completion

### Quest Reward Handling
- Detects completed quests
- Claims quest rewards automatically
- Integrates reward collection into task flow

### State-Driven Task Priorities
Task processing follows a priority structure:

Interrupts  
↓  
Battle Tasks  
↓  
Chest Tasks  
↓  
Business Tasks

Higher-priority events can interrupt lower-priority actions.

### Error Recovery and Anti-Stuck Logic
- Detects failed or missed actions
- Performs retries
- Includes recovery logic for unstable game states
- Reduces loop failures and automation stalls

---

## Architecture

Project uses a modular design:

### Core Components

**Brain**
Central decision engine coordinating task selection.

**GameState**
Tracks live game conditions and available actions.

**Browser Controller**
Handles Playwright browser communication.

**Worker Modules**
Separate task modules for:
- Battles
- Chests
- Business resources
- Interrupts

---

## Technologies Used

- Python
- Playwright
- CustomTkinter
- PyInstaller

Concepts used:
- State-driven automation
- Rule-based decision logic
- Browser automation
- Retry and recovery handling
- Modular task workers

---

## Bot Workflow

Typical automation loop:

1. Check interrupt events  
2. Run battle tasks  
3. Use available skills  
4. Open and process chests  
5. Collect business resources  
6. Claim quest rewards  
7. Return to monitoring loop  
8. Repeat

---

## GUI Features

The desktop interface includes:

- Start / Stop controls
- Battle controls
- Chest controls
- Business task options
- Loot spin window
- Runtime status display
- Configurable automation settings

---

## Installation

### Option 1 — Run Source

Clone repository:

```bash
git clone https://github.com/motaz1993/tokenlords-browser-bot.git
cd tokenlords-browser-bot
```

Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

Run:

```bash
python main.py
```

---

### Option 2 — Compiled Release

Download the latest compiled release from the Releases section and run the executable.

No Python installation required.

---

## How To Use

1. Launch the bot  
2. Connect or open the game browser session  
3. Configure desired automation options  
4. Start the bot  
5. Monitor status panel  
6. Allow the task loop to run automatically

Optional:
- Adjust chest behavior
- Enable or disable business collection
- Configure task preferences

---

## Repository Structure

```text
main.py                 Entry point
brain.py                Decision engine
game_state.py           State tracking
browser_controller.py   Playwright integration
workers/                Task modules
gui/                    Desktop interface
```

(Actual file names may vary.)

---

## Known Limitations

- Designed for supported game flows only
- Browser/game UI changes may require updates
- Some edge cases may need manual review
- Not intended for unsupported game modes

---

## Roadmap

Planned improvements:
- Hotkeys
- Enhanced logging
- Smarter adaptive decisions
- Expanded configuration options
- Usage statistics
- Additional task modules

---

## Project Goals

This project was built as:
- A browser automation project
- A state-driven task automation experiment
- A Python/Playwright portfolio project
- A learning project focused on modular automation architecture

---

## Version

Current Release: v1.2

Initial public release.

---

## License

MIT License

---

## Disclaimer

This repository is published for educational and software automation demonstration purposes.

---

## Author

Developed by **Touched** (Moataz Obaid)  
GitHub: https://github.com/motaz1993

Personal portfolio project focused on Python, browser automation, and state-driven task systems.