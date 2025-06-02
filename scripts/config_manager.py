#!/usr/bin/env python3
"""
Configuration Management Utility for YouTube Analysis Application.

This script helps users:
1. Validate their current configuration
2. Generate a template .env file
3. Check configuration completeness
4. Print current configuration summary
"""

import os
import sys
import argparse
from pathlib import Path

# Add the src directory to the path so we can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'src'))

try:
    from youtube_analysis.core.config import (
        config, validate_config, create_env_template, print_config_summary
    )
except ImportError:
    # Fallback for different project structures
    sys.path.insert(0, str(project_root / 'src' / 'youtube_analysis'))
    from core.config import (
        config, validate_config, create_env_template, print_config_summary
    )


def validate_current_config():
    """Validate the current configuration and print results."""
    print("🔍 Validating Current Configuration...")
    print("=" * 50)
    
    is_valid, missing_vars = validate_config()
    
    if is_valid:
        print("✅ Configuration is valid!")
        print("All required environment variables are set.")
    else:
        print("❌ Configuration is incomplete!")
        print(f"Missing {len(missing_vars)} required variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these variables in your .env file or environment.")
    
    print("\n" + "=" * 50)
    return is_valid


def generate_env_template():
    """Generate a template .env file."""
    print("📝 Generating Environment Template...")
    print("=" * 50)
    
    template_content = create_env_template()
    
    # Write to .env.template file
    template_path = Path('.env.template')
    try:
        with open(template_path, 'w') as f:
            f.write(template_content)
        print(f"✅ Template created: {template_path.absolute()}")
        print("Copy this file to .env and configure your settings.")
    except Exception as e:
        print(f"❌ Error creating template: {e}")
        print("\nTemplate content:")
        print("-" * 30)
        print(template_content)
    
    print("\n" + "=" * 50)


def show_config_summary():
    """Show a summary of the current configuration."""
    print("📊 Current Configuration Summary")
    print("=" * 50)
    print_config_summary()


def check_api_keys():
    """Check which API keys are configured."""
    print("🔑 API Key Status")
    print("=" * 50)
    
    api_keys = {
        "OpenAI": config.api.openai_api_key,
        "Anthropic": config.api.anthropic_api_key,
        "Google/Gemini": config.api.google_api_key or config.api.gemini_api_key,
        "YouTube": config.api.youtube_api_key,
        "Tavily": config.api.tavily_api_key,
        "Supabase URL": config.auth.supabase_url,
        "Supabase Key": config.auth.supabase_key
    }
    
    for name, key in api_keys.items():
        status = "✅ Configured" if key else "❌ Missing"
        print(f"{name:15} {status}")
    
    print("\n" + "=" * 50)


def check_model_availability():
    """Check which models are available based on API keys."""
    print("🤖 Model Availability")
    print("=" * 50)
    
    available_models = []
    
    if config.api.openai_api_key:
        openai_models = [m for m in config.llm.available_models if m.startswith('gpt')]
        available_models.extend(openai_models)
        print(f"OpenAI Models: {', '.join(openai_models)}")
    
    if config.api.anthropic_api_key:
        anthropic_models = [m for m in config.llm.available_models if m.startswith('claude')]
        available_models.extend(anthropic_models)
        print(f"Anthropic Models: {', '.join(anthropic_models)}")
    
    if config.api.google_api_key or config.api.gemini_api_key:
        google_models = [m for m in config.llm.available_models if m.startswith('gemini')]
        available_models.extend(google_models)
        print(f"Google Models: {', '.join(google_models)}")
    
    if not available_models:
        print("❌ No models available - please configure at least one LLM API key")
    else:
        print(f"\n✅ {len(available_models)} models available")
        
        # Check if default model is available
        if config.llm.default_model in available_models:
            print(f"✅ Default model '{config.llm.default_model}' is available")
        else:
            print(f"⚠️  Default model '{config.llm.default_model}' is not available")
            print(f"   Consider changing LLM_DEFAULT_MODEL to one of: {', '.join(available_models[:3])}")
    
    print("\n" + "=" * 50)


def interactive_setup():
    """Interactive configuration setup."""
    print("🛠️  Interactive Configuration Setup")
    print("=" * 50)
    
    print("This will help you set up your configuration step by step.")
    print("Press Ctrl+C at any time to exit.\n")
    
    try:
        # Check if .env exists
        env_path = Path('.env')
        if env_path.exists():
            response = input("📁 .env file already exists. Overwrite? (y/N): ").strip().lower()
            if response != 'y':
                print("Setup cancelled.")
                return
        
        # Generate template
        print("📝 Generating .env template...")
        template_content = create_env_template()
        
        # Write to .env
        with open(env_path, 'w') as f:
            f.write(template_content)
        
        print(f"✅ Created {env_path.absolute()}")
        print("\n📋 Next steps:")
        print("1. Edit the .env file with your API keys and settings")
        print("2. Run 'python scripts/config_manager.py --validate' to check your configuration")
        print("3. Start the application with 'streamlit run src/youtube_analysis_webapp.py'")
        
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
    except Exception as e:
        print(f"❌ Error during setup: {e}")
    
    print("\n" + "=" * 50)


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(
        description="Configuration Management Utility for YouTube Analysis Application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/config_manager.py --validate          # Validate current config
  python scripts/config_manager.py --template          # Generate .env template
  python scripts/config_manager.py --summary           # Show config summary
  python scripts/config_manager.py --setup             # Interactive setup
  python scripts/config_manager.py --all               # Run all checks
        """
    )
    
    parser.add_argument('--validate', action='store_true', 
                       help='Validate current configuration')
    parser.add_argument('--template', action='store_true', 
                       help='Generate .env template file')
    parser.add_argument('--summary', action='store_true', 
                       help='Show configuration summary')
    parser.add_argument('--api-keys', action='store_true', 
                       help='Check API key status')
    parser.add_argument('--models', action='store_true', 
                       help='Check model availability')
    parser.add_argument('--setup', action='store_true', 
                       help='Interactive configuration setup')
    parser.add_argument('--all', action='store_true', 
                       help='Run all checks and show complete status')
    
    args = parser.parse_args()
    
    # If no arguments provided, show help
    if not any(vars(args).values()):
        parser.print_help()
        return
    
    print("🚀 YouTube Analysis Application - Configuration Manager")
    print("=" * 60)
    print()
    
    try:
        if args.setup:
            interactive_setup()
        
        if args.template:
            generate_env_template()
        
        if args.validate or args.all:
            validate_current_config()
        
        if args.summary or args.all:
            show_config_summary()
        
        if args.api_keys or args.all:
            check_api_keys()
        
        if args.models or args.all:
            check_model_availability()
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 