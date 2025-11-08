#!/usr/bin/env python3
"""
Script to run MQTT tests
Wrapper script that can be executed with: python run_tests.py
"""
import sys
import os
import subprocess
import shutil

# ANSI color codes
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color


def print_colored(message, color=GREEN):
    """Print a colored message"""
    print(f"{color}{message}{NC}")


def check_mosquitto():
    """Check if Mosquitto is running"""
    try:
        result = subprocess.run(
            ['pgrep', '-x', 'mosquitto'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        # pgrep not available on this system
        return True  # Assume it's running


def start_mosquitto():
    """Try to start Mosquitto if it's not running"""
    print_colored("Varning: Mosquitto verkar inte köra.", YELLOW)
    print_colored("Försöker starta Mosquitto...", YELLOW)
    
    if shutil.which('systemctl'):
        try:
            subprocess.run(
                ['sudo', 'systemctl', 'start', 'mosquitto'],
                check=False
            )
        except Exception:
            print_colored(
                "Kunde inte starta Mosquitto automatiskt. Starta det manuellt.",
                YELLOW
            )
    else:
        print_colored(
            "Starta Mosquitto manuellt innan testerna körs.",
            YELLOW
        )
    print()


def main():
    """Main function to run the tests"""
    print_colored("=" * 66)
    print_colored("Kör MQTT-tester (Running MQTT tests)")
    print_colored("=" * 66)
    print()
    
    # Check if Mosquitto is running
    if not check_mosquitto():
        start_mosquitto()
    
    # Change to the repository root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    os.chdir(repo_root)
    
    # Set PYTHONPATH to include the repository root
    env = os.environ.copy()
    env['PYTHONPATH'] = repo_root
    
    # Run the tests
    try:
        result = subprocess.run(
            [sys.executable, 'tests/test_mqtt_client.py'] + sys.argv[1:],
            env=env,
            check=False
        )
        
        print()
        if result.returncode == 0:
            print_colored("=" * 66)
            print_colored("Testerna slutförda! (Tests completed!)")
            print_colored("=" * 66)
        else:
            print_colored("=" * 66, RED)
            print_colored("Testerna misslyckades! (Tests failed!)", RED)
            print_colored("=" * 66, RED)
        
        return result.returncode
    
    except Exception as e:
        print_colored(f"Fel vid körning av tester: {e}", RED)
        return 1


if __name__ == '__main__':
    sys.exit(main())
