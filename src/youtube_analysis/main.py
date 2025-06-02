#!/usr/bin/env python3
"""
Comprehensive YouTube Analysis CLI Tool
Feature-complete command-line interface for YouTube video analysis.
"""

import os
import sys
import asyncio
import argparse
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Rich imports for better CLI experience
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.prompt import Prompt, Confirm
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Installing rich for better CLI experience...")
    os.system("pip install rich")
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.progress import Progress, SpinnerColumn, TextColumn
        from rich.prompt import Prompt, Confirm
        from rich.markdown import Markdown
        from rich.syntax import Syntax
        RICH_AVAILABLE = True
    except ImportError:
        RICH_AVAILABLE = False

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from youtube_analysis.core.config import APP_VERSION, validate_config, setup_logging, MAX_GUEST_ANALYSES, CHAT_WELCOME_TEMPLATE
from youtube_analysis.utils.logging import get_logger
from youtube_analysis.adapters.webapp_adapter import WebAppAdapter
from youtube_analysis.services.auth_service import (
    init_supabase, logout
)
from youtube_analysis.services.user_stats_service import get_user_stats, increment_summary_count
from youtube_analysis.core import CacheManager

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configure logging
setup_logging()
logger = get_logger("cli")

class CLISessionManager:
    """Manages CLI session state and settings."""
    
    def __init__(self):
        self.settings = {
            "model": "gpt-4o-mini",
            "temperature": 0.2,
            "use_cache": True,
            "use_optimized": True,
            "analysis_types": ["Summary & Classification"]
        }
        self.analysis_results = None
        self.video_id = None
        self.chat_details = None
        self.chat_messages = []
        self.token_usage = {
            "initial_analysis": {},
            "additional_content": {},
            "chat": {},
            "cumulative": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0}
        }
        self.guest_analysis_count = 0
        
    def update_settings(self, **kwargs):
        self.settings.update(kwargs)
        
    def set_analysis_results(self, results):
        self.analysis_results = results
        if results:
            self.video_id = results.get("video_id")
            self.chat_details = results.get("chat_details")
            
    def add_token_usage(self, category: str, usage: Dict[str, Any], task_key: str = None):
        """Add token usage to tracking."""
        if category == "additional_content" and task_key:
            self.token_usage["additional_content"][task_key] = usage
        else:
            self.token_usage[category] = usage
            
        # Update cumulative
        if isinstance(usage, dict):
            self.token_usage["cumulative"]["total_tokens"] += usage.get("total_tokens", 0)
            self.token_usage["cumulative"]["prompt_tokens"] += usage.get("prompt_tokens", 0)
            self.token_usage["cumulative"]["completion_tokens"] += usage.get("completion_tokens", 0)

class YouTubeAnalysisCLI:
    """Main CLI application class."""
    
    def __init__(self):
        self.console = Console() if RICH_AVAILABLE else None
        self.session = CLISessionManager()
        self.webapp_adapter = WebAppAdapter()
        self.authenticated = False
        self.current_user = None
        
    def print(self, message: str, style: str = None):
        """Print with rich formatting if available."""
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)
            
    def print_panel(self, content: str, title: str = None, style: str = "blue"):
        """Print a panel with rich formatting."""
        if self.console:
            self.console.print(Panel(content, title=title, border_style=style))
        else:
            print(f"\n=== {title} ===" if title else "")
            print(content)
            print("=" * 50)
            
    def print_table(self, data: List[List[str]], headers: List[str], title: str = None):
        """Print a table with rich formatting."""
        if self.console:
            table = Table(title=title)
            for header in headers:
                table.add_column(header)
            for row in data:
                table.add_row(*row)
            self.console.print(table)
        else:
            if title:
                print(f"\n{title}")
            print("-" * 50)
            print(" | ".join(headers))
            print("-" * 50)
            for row in data:
                print(" | ".join(row))
            print("-" * 50)

    def show_welcome(self):
        """Display welcome message and app info."""
        welcome_text = f"""
🎬 YouTube Analysis CLI Tool v{APP_VERSION}
Transform YouTube videos into actionable insights!

Features:
• Intelligent video analysis and summarization
• Generate blog posts, LinkedIn posts, and tweets
• Interactive chat with video content
• Action plan generation
• Smart caching and optimization
• User authentication and statistics
        """
        self.print_panel(welcome_text, "Welcome to YouTube Analysis CLI", "green")
        
    def check_config(self):
        """Check and display configuration status."""
        is_valid, missing_vars = validate_config()
        if not is_valid:
            self.print(f"⚠️  Configuration incomplete. Missing: {', '.join(missing_vars)}", "yellow")
            return False
        self.print("✅ Configuration valid", "green")
        return True
        
    def handle_authentication(self):
        """Handle user authentication."""
        # For CLI, we'll use a simplified approach
        choice = Prompt.ask(
            "Authentication Options",
            choices=["login", "register", "guest", "skip"],
            default="guest"
        ) if RICH_AVAILABLE else input("Choose: (login/register/guest/skip) [guest]: ") or "guest"
        
        if choice == "login":
            self.login()
        elif choice == "register":
            self.register()
        elif choice == "guest":
            self.print("🎁 Running in guest mode (limited analyses)", "cyan")
        else:
            self.print("👤 Continuing without authentication", "yellow")
                
    def login(self):
        """Handle user login."""
        email = Prompt.ask("Email") if RICH_AVAILABLE else input("Email: ")
        password = Prompt.ask("Password", password=True) if RICH_AVAILABLE else input("Password: ")
        
        try:
            supabase = init_supabase()
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                self.authenticated = True
                self.current_user = auth_response.user
                self.print("✅ Login successful!", "green")
                
                # Show user stats
                stats = get_user_stats()
                if stats:
                    self.print(f"📊 Your analyses: {stats.get('summary_count', 0)}", "blue")
            else:
                self.print("❌ Login failed", "red")
        except Exception as e:
            self.print(f"❌ Login failed: {str(e)}", "red")
            
    def register(self):
        """Handle user registration."""
        email = Prompt.ask("Email") if RICH_AVAILABLE else input("Email: ")
        password = Prompt.ask("Password", password=True) if RICH_AVAILABLE else input("Password: ")
        confirm_password = Prompt.ask("Confirm Password", password=True) if RICH_AVAILABLE else input("Confirm Password: ")
        
        if password != confirm_password:
            self.print("❌ Passwords don't match", "red")
            return
            
        try:
            supabase = init_supabase()
            auth_response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                self.authenticated = True
                self.current_user = auth_response.user
                self.print("✅ Registration successful! Please check your email for verification.", "green")
            else:
                self.print("❌ Registration failed", "red")
        except Exception as e:
            self.print(f"❌ Registration failed: {str(e)}", "red")

    def show_settings_menu(self):
        """Display and modify settings."""
        while True:
            self.print_panel(f"""
Current Settings:
🤖 Model: {self.session.settings['model']}
🌡️  Temperature: {self.session.settings['temperature']}
💾 Use Cache: {self.session.settings['use_cache']}
⚡ Optimized Architecture: {self.session.settings['use_optimized']}
📝 Analysis Types: {', '.join(self.session.settings['analysis_types'])}
            """, "Settings", "blue")
            
            choice = Prompt.ask(
                "Settings Options",
                choices=["model", "temperature", "cache", "optimized", "analysis_types", "back"],
                default="back"
            ) if RICH_AVAILABLE else input("Choose setting to change (model/temperature/cache/optimized/analysis_types/back): ") or "back"
            
            if choice == "back":
                break
            elif choice == "model":
                model = Prompt.ask(
                    "Select Model",
                    choices=["gpt-4o-mini", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
                    default=self.session.settings['model']
                ) if RICH_AVAILABLE else input(f"Model ({self.session.settings['model']}): ") or self.session.settings['model']
                self.session.update_settings(model=model)
            elif choice == "temperature":
                try:
                    temp = float(Prompt.ask("Temperature (0.0-1.0)", default=str(self.session.settings['temperature'])) if RICH_AVAILABLE else input(f"Temperature ({self.session.settings['temperature']}): ") or str(self.session.settings['temperature']))
                    if 0.0 <= temp <= 1.0:
                        self.session.update_settings(temperature=temp)
                    else:
                        self.print("❌ Temperature must be between 0.0 and 1.0", "red")
                except ValueError:
                    self.print("❌ Invalid temperature value", "red")
            elif choice == "cache":
                use_cache = Confirm.ask("Use cache?", default=self.session.settings['use_cache']) if RICH_AVAILABLE else input(f"Use cache? (y/n) [{self.session.settings['use_cache']}]: ").lower() in ['y', 'yes', ''] if self.session.settings['use_cache'] else input(f"Use cache? (y/n) [{self.session.settings['use_cache']}]: ").lower() in ['y', 'yes']
                self.session.update_settings(use_cache=use_cache)
            elif choice == "optimized":
                use_optimized = Confirm.ask("Use optimized architecture?", default=self.session.settings['use_optimized']) if RICH_AVAILABLE else input(f"Use optimized? (y/n) [{self.session.settings['use_optimized']}]: ").lower() in ['y', 'yes', ''] if self.session.settings['use_optimized'] else input(f"Use optimized? (y/n) [{self.session.settings['use_optimized']}]: ").lower() in ['y', 'yes']
                self.session.update_settings(use_optimized=use_optimized)
            elif choice == "analysis_types":
                self.select_analysis_types()
                
    def select_analysis_types(self):
        """Select analysis types to generate."""
        available_types = ["Summary & Classification", "Action Plan", "Blog Post", "LinkedIn Post", "X Tweet"]
        
        self.print("📝 Select analysis types to generate:")
        for i, atype in enumerate(available_types, 1):
            selected = "✅" if atype in self.session.settings['analysis_types'] else "❌"
            self.print(f"{i}. {selected} {atype}")
            
        choices = input("Enter numbers separated by commas (e.g., 1,2,3): ")
        try:
            selected_indices = [int(x.strip()) - 1 for x in choices.split(",") if x.strip()]
            selected_types = [available_types[i] for i in selected_indices if 0 <= i < len(available_types)]
            
            if "Summary & Classification" not in selected_types:
                selected_types.insert(0, "Summary & Classification")
                
            self.session.update_settings(analysis_types=selected_types)
            self.print(f"✅ Selected: {', '.join(selected_types)}", "green")
        except (ValueError, IndexError):
            self.print("❌ Invalid selection", "red")

    def analyze_video(self, youtube_url: str = None):
        """Analyze a YouTube video."""
        if not youtube_url:
            youtube_url = Prompt.ask("🎬 Enter YouTube URL") if RICH_AVAILABLE else input("YouTube URL: ")
            
        if not self.webapp_adapter.validate_youtube_url(youtube_url):
            self.print("❌ Invalid YouTube URL", "red")
            return False
            
        # Check guest usage
        if not self.authenticated:
            if self.session.guest_analysis_count >= MAX_GUEST_ANALYSES:
                self.print("🚫 Guest analysis limit reached. Please log in.", "red")
                return False
                
        self.print(f"🔍 Analyzing video: {youtube_url}", "blue")
        
        if RICH_AVAILABLE:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                task = progress.add_task("Analyzing video...", total=None)
                
                try:
                    results, error = asyncio.run(
                        self.webapp_adapter.analyze_video(youtube_url, self.session.settings)
                    )
                except Exception as e:
                    error = str(e)
                    results = None
        else:
            print("Analyzing video...")
            try:
                results, error = asyncio.run(
                    self.webapp_adapter.analyze_video(youtube_url, self.session.settings)
                )
            except Exception as e:
                error = str(e)
                results = None
                
        if error:
            self.print(f"❌ Analysis failed: {error}", "red")
            return False
            
        if results:
            self.session.set_analysis_results(results)
            
            # Track token usage
            if results.get("token_usage"):
                self.session.add_token_usage("initial_analysis", results["token_usage"])
                
            # Increment counters
            if not results.get("cached", False):
                if self.authenticated and self.current_user:
                    try:
                        increment_summary_count(self.current_user.id)
                    except Exception as e:
                        logger.warning(f"Failed to increment summary count: {e}")
                else:
                    self.session.guest_analysis_count += 1
                    
            self.print("✅ Analysis completed successfully!", "green")
            self.display_analysis_results()
            return True
        else:
            self.print("❌ Analysis failed - no results returned", "red")
            return False

    def display_analysis_results(self):
        """Display analysis results."""
        if not self.session.analysis_results:
            self.print("❌ No analysis results available", "red")
            return
            
        results = self.session.analysis_results
        video_info = results.get("video_info", {})
        
        # Video info
        self.print_panel(f"""
📺 Title: {video_info.get('title', 'Unknown')}
🆔 Video ID: {results.get('video_id', 'Unknown')}
🔗 URL: {results.get('youtube_url', 'Unknown')}
⏱️  Analysis Time: {results.get('analysis_time', 'Unknown')}s
💾 Cached: {'Yes' if results.get('cached') else 'No'}
        """, "Video Information", "blue")
        
        # Analysis outputs
        task_outputs = results.get("task_outputs", {})
        if not task_outputs:
            self.print("⚠️  No task outputs found", "yellow")
            return
            
        for task_name, output in task_outputs.items():
            if output and hasattr(output, 'content'):
                content = output.content
            elif isinstance(output, dict):
                content = output.get('content', str(output))
            else:
                content = str(output)
                
            display_name = self.get_display_name(task_name)
            
            if self.console:
                self.console.print(f"\n📋 {display_name}", style="bold cyan")
                self.console.print("-" * 50)
                
                if task_name in ["write_blog_post", "write_linkedin_post"]:
                    # Display as markdown for better formatting
                    self.console.print(Markdown(content))
                else:
                    self.console.print(content)
            else:
                print(f"\n📋 {display_name}")
                print("-" * 50)
                print(content)
                
    def get_display_name(self, task_name: str) -> str:
        """Get display name for task."""
        name_map = {
            "classify_and_summarize_content": "Summary & Classification",
            "analyze_and_plan_content": "Action Plan",
            "write_blog_post": "Blog Post",
            "write_linkedin_post": "LinkedIn Post",
            "write_tweet": "X Tweet"
        }
        return name_map.get(task_name, task_name)

    def generate_additional_content(self):
        """Generate additional content types."""
        if not self.session.analysis_results:
            self.print("❌ No initial analysis available. Please analyze a video first.", "red")
            return
            
        available_types = ["Action Plan", "Blog Post", "LinkedIn Post", "X Tweet"]
        current_outputs = self.session.analysis_results.get("task_outputs", {})
        
        # Filter out already generated types
        missing_types = []
        for atype in available_types:
            task_key = {
                "Action Plan": "analyze_and_plan_content",
                "Blog Post": "write_blog_post", 
                "LinkedIn Post": "write_linkedin_post",
                "X Tweet": "write_tweet"
            }.get(atype)
            
            if task_key not in current_outputs:
                missing_types.append(atype)
                
        if not missing_types:
            self.print("✅ All content types already generated!", "green")
            return
            
        self.print("📝 Available content types to generate:")
        for i, ctype in enumerate(missing_types, 1):
            self.print(f"{i}. {ctype}")
            
        try:
            choice = int(Prompt.ask("Select content type", choices=[str(i) for i in range(1, len(missing_types) + 1)]) if RICH_AVAILABLE else input("Select number: "))
            selected_type = missing_types[choice - 1]
        except (ValueError, IndexError):
            self.print("❌ Invalid selection", "red")
            return
            
        youtube_url = self.session.analysis_results.get("youtube_url")
        video_id = self.session.analysis_results.get("video_id")
        transcript = self.session.analysis_results.get("transcript")
        
        self.print(f"🔄 Generating {selected_type}...", "blue")
        
        try:
            content, error, token_usage = asyncio.run(
                self.webapp_adapter.generate_additional_content(
                    youtube_url, video_id, transcript, selected_type, self.session.settings
                )
            )
            
            if error:
                self.print(f"❌ Failed to generate {selected_type}: {error}", "red")
            elif content:
                self.print(f"✅ {selected_type} generated successfully!", "green")
                
                # Track token usage
                if token_usage:
                    task_key = {
                        "Action Plan": "analyze_and_plan_content",
                        "Blog Post": "write_blog_post",
                        "LinkedIn Post": "write_linkedin_post", 
                        "X Tweet": "write_tweet"
                    }.get(selected_type)
                    self.session.add_token_usage("additional_content", token_usage, task_key)
                
                # Update results and display
                self.session.analysis_results["task_outputs"][task_key] = type('TaskOutput', (), {'content': content})()
                self.display_single_result(selected_type, content)
            else:
                self.print(f"❌ No content generated for {selected_type}", "red")
                
        except Exception as e:
            self.print(f"❌ Error generating {selected_type}: {str(e)}", "red")

    def display_single_result(self, content_type: str, content: str):
        """Display a single content result."""
        if self.console:
            self.console.print(f"\n📋 {content_type}", style="bold cyan")
            self.console.print("-" * 50)
            
            if content_type in ["Blog Post", "LinkedIn Post"]:
                self.console.print(Markdown(content))
            else:
                self.console.print(content)
        else:
            print(f"\n📋 {content_type}")
            print("-" * 50)
            print(content)

    def start_chat_session(self):
        """Start interactive chat session."""
        if not self.session.video_id:
            self.print("❌ No video analyzed. Please analyze a video first.", "red")
            return
            
        if not self.session.chat_details:
            self.print("❌ Chat not available for this video.", "red")
            return
            
        video_title = self.session.analysis_results.get("video_info", {}).get("title", "this video")
        
        self.print_panel(f"""
💬 Chat Session Started
You can now ask questions about: {video_title}

Commands:
• Type your questions naturally
• 'exit' or 'quit' to end chat
• 'clear' to clear chat history
        """, "Interactive Chat", "green")
        
        # Initialize chat if empty
        if not self.session.chat_messages:
            welcome_msg = CHAT_WELCOME_TEMPLATE.format(video_title=video_title)
            self.session.chat_messages.append({"role": "assistant", "content": welcome_msg})
            self.print(f"🤖 Assistant: {welcome_msg}", "blue")
            
        while True:
            try:
                user_input = input("\n👤 You: ").strip()
                
                if user_input.lower() in ['exit', 'quit']:
                    self.print("👋 Chat session ended.", "yellow")
                    break
                elif user_input.lower() == 'clear':
                    self.session.chat_messages = []
                    self.print("🧹 Chat history cleared.", "yellow")
                    continue
                elif not user_input:
                    continue
                    
                self.session.chat_messages.append({"role": "user", "content": user_input})
                
                # Get AI response
                self.print("🤖 Assistant is thinking...", "blue")
                
                try:
                    full_response = ""
                    chat_token_usage = None
                    
                    async def get_response():
                        nonlocal full_response, chat_token_usage
                        async for chunk, token_usage in self.webapp_adapter.get_chat_response_stream(
                            self.session.video_id, 
                            self.session.chat_messages[:-1], 
                            user_input, 
                            self.session.settings
                        ):
                            if chunk:
                                full_response += chunk
                            if token_usage:
                                chat_token_usage = token_usage
                                
                    asyncio.run(get_response())
                    
                    self.session.chat_messages.append({"role": "assistant", "content": full_response})
                    
                    # Track token usage
                    if chat_token_usage:
                        self.session.add_token_usage("chat", chat_token_usage)
                    
                    self.print(f"🤖 Assistant: {full_response}", "blue")
                    
                except Exception as e:
                    error_msg = f"Sorry, an error occurred: {str(e)}"
                    self.session.chat_messages.append({"role": "assistant", "content": error_msg})
                    self.print(f"🤖 Assistant: {error_msg}", "red")
                    
            except KeyboardInterrupt:
                self.print("\n👋 Chat session ended.", "yellow")
                break
            except EOFError:
                self.print("\n👋 Chat session ended.", "yellow")
                break

    def show_token_usage(self):
        """Display token usage statistics."""
        usage = self.session.token_usage
        cumulative = usage["cumulative"]
        
        # Main usage stats
        data = [
            ["Total Tokens", f"{cumulative['total_tokens']:,}"],
            ["Prompt Tokens", f"{cumulative['prompt_tokens']:,}"],
            ["Completion Tokens", f"{cumulative['completion_tokens']:,}"]
        ]
        
        self.print_table(data, ["Metric", "Count"], "📈 Overall Token Usage")
        
        # Detailed breakdown
        if usage["initial_analysis"]:
            initial = usage["initial_analysis"]
            self.print(f"\n📊 Initial Analysis: {initial.get('total_tokens', 0):,} tokens", "blue")
            
        if usage["additional_content"]:
            self.print("\n🎯 Additional Content:", "blue")
            for task, task_usage in usage["additional_content"].items():
                display_name = self.get_display_name(task)
                self.print(f"  • {display_name}: {task_usage.get('total_tokens', 0):,} tokens")
                
        if usage["chat"] and usage["chat"].get("total_tokens", 0) > 0:
            chat = usage["chat"]
            self.print(f"\n💬 Chat: {chat.get('total_tokens', 0):,} tokens", "blue")
            
        # Cost estimation using dynamic cost service
        model = self.session.settings.get("model", "gpt-4o-mini")
        
        try:
            from youtube_analysis.services.cost_service import calculate_cost_for_tokens
            from youtube_analysis.core.config import config
            
            if config.api.enable_dynamic_costs and config.api.glama_api_key:
                estimated_cost = calculate_cost_for_tokens(
                    model, 
                    cumulative["prompt_tokens"], 
                    cumulative["completion_tokens"]
                )
                cost_source = "Glama.ai"
            else:
                # Fall back to static calculation
                from youtube_analysis.core.config import get_model_cost
                cost_per_1k = get_model_cost(model)
                estimated_cost = (cumulative["total_tokens"] / 1000) * cost_per_1k
                cost_source = "static"
                
        except Exception as e:
            # Fall back to static calculation
            cost_estimates = {
                "gpt-4o-mini": 0.00015,
                "gemini-2.0-flash": 0.0001,
                "gemini-2.0-flash-lite": 0.00005,
            }
            cost_per_1k = cost_estimates.get(model, 0.0001)
            estimated_cost = (cumulative["total_tokens"] / 1000) * cost_per_1k
            cost_source = "static (fallback)"
        
        self.print(f"\n💰 Estimated Cost: ${estimated_cost:.6f} ({model}) - {cost_source}", "green")

    def save_results(self):
        """Save analysis results to file."""
        if not self.session.analysis_results:
            self.print("❌ No analysis results to save", "red")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_id = self.session.video_id or "unknown"
        filename = f"youtube_analysis_{video_id}_{timestamp}.json"
        
        output_dir = Path("analysis_outputs")
        output_dir.mkdir(exist_ok=True)
        filepath = output_dir / filename
        
        try:
            # Prepare data for saving
            save_data = {
                "timestamp": timestamp,
                "video_info": self.session.analysis_results.get("video_info", {}),
                "settings": self.session.settings,
                "task_outputs": {},
                "token_usage": self.session.token_usage,
                "chat_messages": self.session.chat_messages
            }
            
            # Convert task outputs to serializable format
            task_outputs = self.session.analysis_results.get("task_outputs", {})
            for task_name, output in task_outputs.items():
                if output and hasattr(output, 'content'):
                    save_data["task_outputs"][task_name] = output.content
                elif isinstance(output, dict):
                    save_data["task_outputs"][task_name] = output.get('content', str(output))
                else:
                    save_data["task_outputs"][task_name] = str(output)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
                
            self.print(f"✅ Results saved to: {filepath}", "green")
            
        except Exception as e:
            self.print(f"❌ Error saving results: {str(e)}", "red")

    def clear_cache(self):
        """Clear cache for current video."""
        if not self.session.video_id:
            self.print("❌ No video ID available for cache clearing", "red")
            return
            
        try:
            self.webapp_adapter.clear_cache_for_video(self.session.video_id)
            self.print(f"✅ Cache cleared for video {self.session.video_id}", "green")
        except Exception as e:
            self.print(f"❌ Error clearing cache: {str(e)}", "red")

    def show_main_menu(self):
        """Display main menu and handle navigation."""
        while True:
            status = "🟢 Authenticated" if self.authenticated else "🟡 Guest Mode"
            video_status = f"📺 Video: {self.session.video_id}" if self.session.video_id else "📺 No video analyzed"
            
            menu_text = f"""
Status: {status} | {video_status}

Main Menu:
1. 🎬 Analyze YouTube Video
2. ⚙️  Settings
3. 📋 View Results
4. 🔄 Generate Additional Content  
5. 💬 Start Chat Session
6. 📊 Show Token Usage
7. 💾 Save Results
8. 🧹 Clear Cache
9. 👤 Account Management
0. 🚪 Exit
            """
            
            self.print_panel(menu_text, "YouTube Analysis CLI", "cyan")
            
            choice = Prompt.ask("Select option", choices=[str(i) for i in range(10)]) if RICH_AVAILABLE else input("Choose option (0-9): ")
            
            try:
                choice = int(choice)
                
                if choice == 1:
                    self.analyze_video()
                elif choice == 2:
                    self.show_settings_menu()
                elif choice == 3:
                    self.display_analysis_results()
                elif choice == 4:
                    self.generate_additional_content()
                elif choice == 5:
                    self.start_chat_session()
                elif choice == 6:
                    self.show_token_usage()
                elif choice == 7:
                    self.save_results()
                elif choice == 8:
                    self.clear_cache()
                elif choice == 9:
                    self.account_management()
                elif choice == 0:
                    self.print("👋 Goodbye!", "green")
                    break
                else:
                    self.print("❌ Invalid choice", "red")
                    
            except ValueError:
                self.print("❌ Please enter a valid number", "red")
                
            if choice != 0:
                input("\nPress Enter to continue...")

    def account_management(self):
        """Handle account management options."""
        if self.authenticated:
            stats = get_user_stats()
            user_info = f"""
👤 User: {self.current_user.email}
📊 Analyses: {stats.get('summary_count', 0) if stats else 0}
            """
            self.print_panel(user_info, "Account Information", "blue")
            
            if Confirm.ask("Logout?") if RICH_AVAILABLE else input("Logout? (y/n): ").lower() in ['y', 'yes']:
                try:
                    supabase = init_supabase()
                    supabase.auth.sign_out()
                    self.authenticated = False
                    self.current_user = None
                    self.print("👋 Logged out successfully", "green")
                except Exception as e:
                    self.print(f"❌ Logout failed: {str(e)}", "red")
        else:
            choice = Prompt.ask(
                "Account Options",
                choices=["login", "register", "back"],
                default="back"
            ) if RICH_AVAILABLE else input("Choose: (login/register/back) [back]: ") or "back"
            
            if choice == "login":
                self.login()
            elif choice == "register":
                self.register()

    def run_with_args(self, args):
        """Run CLI with command line arguments."""
        if args.url:
            # Direct analysis mode
            self.print("🚀 Quick Analysis Mode", "cyan")
            if self.analyze_video(args.url):
                if args.save:
                    self.save_results()
                if args.chat:
                    self.start_chat_session()
        else:
            # Interactive mode
            self.show_welcome()
            self.check_config()
            self.handle_authentication()
            self.show_main_menu()

def setup_argument_parser():
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="YouTube Analysis CLI Tool",
        epilog="For interactive mode, run without arguments."
    )
    
    parser.add_argument(
        "url", 
        nargs="?", 
        help="YouTube URL to analyze (optional, for quick analysis)"
    )
    
    parser.add_argument(
        "--model",
        choices=["gpt-4o-mini", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
        default="gpt-4o-mini",
        help="AI model to use (default: gpt-4o-mini)"
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Model temperature (0.0-1.0, default: 0.2)"
    )
    
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable caching"
    )
    
    parser.add_argument(
        "--save",
        action="store_true", 
        help="Save results to file after analysis"
    )
    
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Start chat session after analysis"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"YouTube Analysis CLI v{APP_VERSION}"
    )
    
    return parser

def main():
    """Main entry point."""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    try:
        cli = YouTubeAnalysisCLI()
        
        # Apply command line settings
        if args.model:
            cli.session.update_settings(model=args.model)
        if args.temperature:
            cli.session.update_settings(temperature=args.temperature)
        if args.no_cache:
            cli.session.update_settings(use_cache=False)
            
        cli.run_with_args(args)
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {str(e)}")
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 