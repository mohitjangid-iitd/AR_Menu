import os
import subprocess
import sys

def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    print("Installing pytest-cov if not present...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pytest-cov"], check=True)
    except subprocess.CalledProcessError:
        print("[ERROR] Failed to install pytest-cov.")
        sys.exit(1)
        
    print("\nRunning pytest with coverage...")
    env = os.environ.copy()
    env["SECRET_KEY"] = "test"
    
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "--cov=.", "--cov-report=term-missing", "--cov-report=html"],
            env=env,
            check=False
        )
    except KeyboardInterrupt:
        print("\n[STOPPED] Coverage check interrupted.")
    except Exception as e:
        print(f"\n[ERROR] Error running coverage: {e}")
        
    print("\nCoverage check complete!")
    print("You can view the detailed line-by-line HTML report by opening 'htmlcov/index.html' in your browser.")

if __name__ == "__main__":
    main()
