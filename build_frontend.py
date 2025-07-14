
#!/usr/bin/env python3
import subprocess
import os
import sys

def run_command(command, cwd=None):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(command, shell=True, cwd=cwd, check=True, 
                              capture_output=True, text=True)
        print(f"✓ {command}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"✗ {command}")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("Building IDCR Frontend...")
    
    # Change to frontend directory
    frontend_dir = "frontend"
    
    if not os.path.exists(frontend_dir):
        print(f"Error: {frontend_dir} directory not found")
        sys.exit(1)
    
    # Install dependencies
    print("\n1. Installing dependencies...")
    if not run_command("npm install", cwd=frontend_dir):
        print("Failed to install dependencies")
        sys.exit(1)
    
    # Build the frontend
    print("\n2. Building React app...")
    if not run_command("npm run build", cwd=frontend_dir):
        print("Failed to build React app")
        sys.exit(1)
    
    print("\n✓ Frontend build complete!")
    print("You can now run 'python main.py' to serve the application")

if __name__ == "__main__":
    main()
