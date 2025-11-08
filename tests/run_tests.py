#!/usr/bin/env python3
"""
Script to run MQTT tests
Wrapper script that can be executed with: python run_tests.py
"""
import sys
import os
import subprocess

# ANSI color codes
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color


def print_colored(message, color=GREEN):
    """Print a colored message"""
    print(f"{color}{message}{NC}")


def check_config_file():
    """Check if config.yaml exists"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    config_path = os.path.join(repo_root, 'config.yaml')
    
    if not os.path.exists(config_path):
        print_colored("=" * 66, YELLOW)
        print_colored("Varning: config.yaml saknas!", YELLOW)
        print_colored("Skapa config.yaml från config.example.yaml och konfigurera MQTT-inställningar.", YELLOW)
        print_colored("=" * 66, YELLOW)
        print()
        return False
    return True


def main():
    """Main function to run the tests"""
    print_colored("=" * 66)
    print_colored("Kör MQTT-tester mot HiveMQ Cloud (Running MQTT tests against HiveMQ Cloud)")
    print_colored("=" * 66)
    print()
    
    # Check if config.yaml exists
    if not check_config_file():
        print_colored("Testerna kräver config.yaml med MQTT-inställningar.", RED)
        return 1
    
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
