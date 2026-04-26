import os
import subprocess
import sys
import webbrowser
import time

def main():
    print("Starting VERITAS-Omega Backend...")
    
    # Path to the virtual env python
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    
    if not os.path.exists(venv_python):
        print("Virtual environment not found. Please run 'python -m venv .venv' and install requirements.")
        sys.exit(1)

    # Start FastAPI server
    server_process = subprocess.Popen(
        [venv_python, "-m", "uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000", "--env-file", ".env"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    print("Backend is starting on http://localhost:8000...")
    
    # Wait for server to boot
    time.sleep(3)
    
    # Start Streamlit UI
    print("Starting Premium Streamlit UI...")
    ui_process = subprocess.Popen(
        [venv_python, "-m", "streamlit", "run", "ui/app.py", "--server.port", "8501", "--server.headless", "true"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    print("UI is starting on http://localhost:8501...")
    time.sleep(2)
    webbrowser.open("http://localhost:8501")

    try:
        server_process.wait()
        ui_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down VERITAS-Omega...")
        server_process.terminate()
        ui_process.terminate()
        server_process.wait()
        ui_process.wait()

if __name__ == "__main__":
    main()
