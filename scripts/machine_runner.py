#!/usr/bin/env python3
"""
One-at-a-Time Machine Runner
Main orchestrator that manages the complete workflow
"""

import os
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

class MachineRunner:
    def __init__(self):
        self.status_file = 'status.md'
        self.queue_file = 'queue.json'
        self.config_file = 'config.json'
        self.ensure_config()
    
    def ensure_config(self):
        """Ensure configuration file exists"""
        if not os.path.exists(self.config_file):
            default_config = {
                "github_token": "",
                "openai_api_key": "",
                "scan_languages": ["python", "javascript", "java", "go", "rust"],
                "max_repos_per_language": 10,
                "min_impact_score": 25,
                "node_id": f"node_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            }
            with open(self.config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            print(f"Created default config: {self.config_file}")
            print("Please update with your API keys!")
    
    def load_config(self):
        """Load configuration"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
    
    def read_status(self):
        """Read current status"""
        if os.path.exists(self.status_file):
            with open(self.status_file, 'r') as f:
                return f.read()
        return ""
    
    def determine_next_step(self):
        """Determine what step to execute next"""
        status = self.read_status()
        
        if not os.path.exists(self.queue_file):
            return "scan"
        
        if "Specification Complete" in status:
            return "implement"
        elif "Issue Discovery Complete" in status:
            return "spec"
        elif os.path.exists(self.queue_file):
            # Check if we have a fresh queue
            with open(self.queue_file, 'r') as f:
                queue_data = json.load(f)
            if queue_data.get('issues'):
                return "spec"
        
        return "scan"
    
    def run_scanner(self):
        """Execute the GitHub issue scanner"""
        print("🔍 Running GitHub Issue Scanner...")
        try:
            result = subprocess.run([sys.executable, 'scanner.py'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Scanner completed successfully")
                return True
            else:
                print(f"❌ Scanner failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error running scanner: {e}")
            return False
    
    def run_spec_generator(self):
        """Execute the specification generator"""
        print("🔮 Running Specification Generator...")
        try:
            result = subprocess.run([sys.executable, 'spec_generator.py'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Specification generated successfully")
                return True
            else:
                print(f"❌ Spec generation failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error running spec generator: {e}")
            return False
    
    def run_implementer(self):
        """Execute the solution implementer"""
        print("🛠️  Running Solution Implementer...")
        print("⚠️  Implementation step not yet built")
        print("📋 Current task: Build the implementer.py module")
        
        # For now, just update status to indicate this step is needed
        status = f"""# One-at-a-Time Machine Status

## Current Phase: Implementation Required
- **Last Update**: {datetime.now().isoformat()}
- **Status**: Ready for implementation
- **Next Step**: Build implementer.py module

## Implementation Module Needed
The system needs an implementer.py that can:
1. Read the generated specification
2. Analyze the target repository
3. Generate solution code
4. Create tests
5. Validate the solution

## Current State
- Scanner: ✅ Complete
- Spec Generator: ✅ Complete  
- Implementer: ⚠️ Needs Development
- Tester: ⚠️ Needs Development
- Coordinator: ⚠️ Needs Development
"""
        
        with open(self.status_file, 'w') as f:
            f.write(status)
        
        return False
    
    def run_continuous(self):
        """Run the machine in continuous mode"""
        print("🤖 One-at-a-Time Machine - Continuous Mode")
        print("=" * 50)
        
        config = self.load_config()
        
        # Set environment variables from config
        if config.get('github_token'):
            os.environ['GITHUB_TOKEN'] = config['github_token']
        if config.get('openai_api_key'):
            os.environ['OPENAI_API_KEY'] = config['openai_api_key']
        
        while True:
            try:
                next_step = self.determine_next_step()
                print(f"\n🎯 Next Step: {next_step}")
                
                if next_step == "scan":
                    if self.run_scanner():
                        continue
                    else:
                        break
                
                elif next_step == "spec":
                    if self.run_spec_generator():
                        continue
                    else:
                        break
                
                elif next_step == "implement":
                    if self.run_implementer():
                        continue
                    else:
                        break
                
                else:
                    print("❓ Unknown step, stopping")
                    break
                    
            except KeyboardInterrupt:
                print("\n🛑 Stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in main loop: {e}")
                break
    
    def run_single_step(self):
        """Run a single step of the machine"""
        print("🤖 One-at-a-Time Machine - Single Step")
        print("=" * 50)
        
        config = self.load_config()
        
        # Set environment variables from config
        if config.get('github_token'):
            os.environ['GITHUB_TOKEN'] = config['github_token']
        if config.get('openai_api_key'):
            os.environ['OPENAI_API_KEY'] = config['openai_api_key']
        
        next_step = self.determine_next_step()
        print(f"🎯 Executing: {next_step}")
        
        if next_step == "scan":
            self.run_scanner()
        elif next_step == "spec":
            self.run_spec_generator()
        elif next_step == "implement":
            self.run_implementer()
        else:
            print("❓ No clear next step")
    
    def show_status(self):
        """Display current machine status"""
        print("📊 One-at-a-Time Machine Status")
        print("=" * 50)
        
        status = self.read_status()
        if status:
            print(status)
        else:
            print("No status file found. Machine not yet started.")
        
        # Show queue status
        if os.path.exists(self.queue_file):
            with open(self.queue_file, 'r') as f:
                queue_data = json.load(f)
            print(f"\n📋 Queue: {len(queue_data.get('issues', []))} issues")
        else:
            print("\n📋 Queue: No issues found")

def main():
    """Main execution function"""
    runner = MachineRunner()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "continuous":
            runner.run_continuous()
        elif command == "step":
            runner.run_single_step()
        elif command == "status":
            runner.show_status()
        else:
            print("Usage: python machine.py [continuous|step|status]")
    else:
        runner.run_single_step()

if __name__ == "__main__":
    main()
