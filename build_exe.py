"""Build script to create standalone executable for TokenLords Bot."""
import PyInstaller.__main__

def build():
    args = [
        "main.py",
        "--name=TokenLordsBot - 1.2",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--hidden-import=customtkinter",
        "--hidden-import=playwright",
        "--hidden-import=asyncio",
        "--hidden-import=tkinter",
        "--add-data=workers;workers",
    ]
    print("Building TokenLords Bot - 1.2 executable...")
    PyInstaller.__main__.run(args)
    print("Build complete! dist/TokenLordsBot - 1.2.exe")

if __name__ == "__main__":
    build()
