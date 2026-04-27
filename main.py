"""TokenLords Pro - Brain Architecture
Entry point for the game automation tool.
"""
import os
import sys

# Quiet Node.js deprecation warnings
os.environ.setdefault("NODE_OPTIONS", "--no-deprecation")

import asyncio
from brain import Brain
from ui import TokenLordsUI


def main():
    """Main entry point."""
    # Create brain instance
    brain = Brain()
    
    # Create and run UI
    app = TokenLordsUI(brain)
    app.mainloop()


if __name__ == "__main__":
    main()
