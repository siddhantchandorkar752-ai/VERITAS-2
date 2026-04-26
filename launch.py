import os
import subprocess
import sys
import webbrowser
import time

def main():
    print("Starting VERITAS-Ω Backend...")
    
    # Path to the virtual env python
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    
    if not os.path.exists(venv_python):
        print("Virtual environment not found. Please run 'python -m venv .venv' and install requirements.")
        sys.exit(1)

    # Start FastAPI server
    server_process = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    print("Backend is starting on http://localhost:8000...")
    
    # Wait for server to boot
    time.sleep(3)
    
    # Open UI in browser
    ui_path = os.path.abspath(os.path.join("ui", "index.html"))
    print(f"Opening UI: {ui_path}")
    webbrowser.open(f"file://{ui_path}")

    try:
        server_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down VERITAS-Ω...")
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    main()
