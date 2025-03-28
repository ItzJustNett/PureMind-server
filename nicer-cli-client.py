#!/usr/bin/env python3
"""
Interactive CLI Client for the Lessons API
A modern, user-friendly command-line interface for the Lessons API
"""
import os
import sys
import json
import time
import getpass
import requests
from typing import Dict, List, Optional, Any, Tuple

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.prompt import Prompt, Confirm
    import questionary
    from questionary import Style
    import base64
    import tempfile
    import pyaudio
    import wave
except ImportError:
    print("Required packages not found. Please install them with:")
    print("pip install rich questionary pyaudio")
    sys.exit(1)

# Configuration
CONFIG_DIR = os.path.expanduser("~/.lessons-cli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
API_BASE_URL = "http://localhost:5000/api"  # Default API URL

# Initialize rich console
console = Console()

# Custom style for questionary
custom_style = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'fg:white bold'),
    ('answer', 'fg:green bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
    ('selected', 'fg:green bold'),
    ('separator', 'fg:cyan'),
    ('instruction', 'fg:white'),
    ('text', 'fg:white'),
    ('disabled', 'fg:gray'),
])

# ASCII Art logo
LOGO = """
    __                                           _____  __    ___ 
   / /   ___  ____ _________  ____  _____      / ___/ / /   /_ _\\
  / /   / _ \\/ ___/ ___/ __ \\/ __ \\/ ___/_____/ /__  / /   / __  \\
 / /___/  __(__  |__  ) /_/ / / / (__  )_____/ ___/ / /___/ /_/  /
/_____/\\___/____/____/\\____/_/ /_/____/     /_/    /_____/\\____/
"""

# Emoji icons for different types of output
ICONS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "login": "🔑",
    "user": "👤",
    "lesson": "📚",
    "search": "🔍",
    "test": "📝",
    "cat": "🐱",
    "conspect": "📋",
    "tts": "🔊",
    "stt": "🎤",
    "cost": "💰",
}

def ensure_config_dir():
    """Ensure the config directory exists"""
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

def load_config() -> Dict:
    """Load the configuration from disk"""
    ensure_config_dir()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def save_config(config: Dict):
    """Save the configuration to disk"""
    ensure_config_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def get_auth_header(config: Dict) -> Optional[Dict]:
    """Get the Authorization header if a token exists"""
    token = config.get('token')
    if token:
        return {"Authorization": f"Bearer {token}"}
    return None

def handle_response(response: requests.Response) -> Tuple[Any, bool]:
    """Handle the API response and return the data and success flag"""
    try:
        data = response.json()
        if response.status_code >= 400:
            console.print(f"{ICONS['error']} API Error ({response.status_code}): {data.get('error', 'Unknown error')}", style="bold red")
            return data, False
        return data, True
    except json.JSONDecodeError:
        console.print(f"{ICONS['error']} Invalid JSON response:", style="bold red")
        console.print(response.text, style="red")
        return None, False
    except Exception as e:
        console.print(f"{ICONS['error']} Error processing response: {str(e)}", style="bold red")
        return None, False

def check_login_or_exit():
    """Check if the user is logged in, if not, show a message and exit"""
    config = load_config()
    if not config.get('token'):
        console.print(Panel(f"{ICONS['warning']} You need to login first. Use 'login' command.", 
                          title="Authentication Required", 
                          border_style="yellow", 
                          expand=False))
        sys.exit(1)
    return config

def show_dashboard():
    """Show the main dashboard with user info and stats"""
    config = load_config()
    token = config.get('token')
    
    console.print(LOGO, style="bold cyan")
    console.print("\n")
    
    if not token:
        console.print(Panel(
            "[bold]You are not logged in.[/bold]\n\n"
            "Use the 'login' command to authenticate or 'register' to create a new account.",
            title="Welcome to Lessons CLI",
            border_style="cyan",
            expand=False
        ))
        return
    
    try:
        headers = get_auth_header(config)
        
        # Get user info
        with console.status(f"[cyan]Loading user info...", spinner="dots"):
            user_response = requests.get(f"{API_BASE_URL}/auth/me", headers=headers)
            user_data, user_success = handle_response(user_response)
        
        if not user_success:
            console.print(f"{ICONS['warning']} Could not load user info. Your session may have expired.", style="bold yellow")
            return
            
        # Get profile
        with console.status(f"[cyan]Loading profile...", spinner="dots"):
            profile_response = requests.get(f"{API_BASE_URL}/profiles/me", headers=headers)
            profile_data, profile_success = handle_response(profile_response)
        
        # Get lesson count
        with console.status(f"[cyan]Loading lessons data...", spinner="dots"):
            lessons_response = requests.get(f"{API_BASE_URL}/lessons")
            lessons_data, lessons_success = handle_response(lessons_response)
        
        # Display user info
        console.print(Panel(
            f"[bold green]Logged in as:[/bold green] [yellow]{user_data.get('username', 'Unknown')}[/yellow]\n"
            f"[bold green]User ID:[/bold green] [yellow]{user_data.get('id', 'Unknown')}[/yellow]",
            title=f"{ICONS['user']} User Information",
            border_style="green",
            expand=False
        ))
        
        # Display profile if it exists
        if profile_success and profile_data and not isinstance(profile_data, dict) or not profile_data.get('error'):
            cat_id = profile_data.get('cat_id', 'None')
            cat_emoji = "😺" if cat_id == 0 else "😸" if cat_id == 1 else "😻" if cat_id == 10 else "🐱"
            
            # Get illness information
            illness_id = profile_data.get('illness_id', 0)
            illness_name = profile_data.get('illness_name', 'None')
            illness_name_ua = profile_data.get('illness_name_ua', 'Немає')
            
            console.print(Panel(
                f"[bold]Name:[/bold] {profile_data.get('name', 'Not set')}\n"
                f"[bold]About:[/bold] {profile_data.get('about', 'Not set')}\n"
                f"[bold]Cat:[/bold] {cat_emoji} (ID: {cat_id})\n"
                f"[bold]Accessibility Needs:[/bold] {illness_name} ({illness_name_ua}) [ID: {illness_id}]",
                title=f"{ICONS['cat']} Profile",
                border_style="cyan",
                expand=False
            ))
        
        # Display lesson stats
        if lessons_success:
            lesson_count = lessons_data.get('count', 0)
            console.print(Panel(
                f"[bold]Total Lessons:[/bold] {lesson_count}",
                title=f"{ICONS['lesson']} Lessons",
                border_style="blue",
                expand=False
            ))
            
        console.print()
        console.print("[bold cyan]What would you like to do?[/bold cyan]")
        console.print()
        
    except Exception as e:
        console.print(f"{ICONS['error']} Error loading dashboard: {str(e)}", style="bold red")

def main_menu():
    """Show the main menu and handle user selection"""
    config = load_config()
    is_logged_in = bool(config.get('token'))
    
    choices = []
    
    if not is_logged_in:
        choices.extend([
            questionary.Separator("=== Authentication ==="),
            "Login",
            "Register",
        ])
    else:
        choices.extend([
            questionary.Separator("=== Account ==="),
            "Logout",
            "View Profile",
            "Update Profile",
            questionary.Separator("=== Lessons ==="),
            "List Lessons",
            "Search Lessons",
            "View Lesson Details",
            "Add New Lesson",
            questionary.Separator("=== AI Features ==="),
            "Generate Lesson Summary",
            "Generate Course Test",
            questionary.Separator("=== Speech Features ==="),
            "Text to Speech",
            "Speech to Text",
        ])
    
    choices.extend([
        questionary.Separator("=== System ==="),
        "Test API Connection",
        "Show Usage Cost",
        "Exit",
    ])
    
    choice = questionary.select(
        "Select an option:",
        choices=choices,
        style=custom_style
    ).ask()
    
    if choice is None or choice == "Exit":
        console.print(f"\n{ICONS['info']} Goodbye!", style="bold blue")
        sys.exit(0)
        
    return choice.lower().replace(" ", "_")

def register():
    """Register a new user"""
    console.print(Panel(f"{ICONS['user']} Register a New Account", border_style="cyan", expand=False))
    
    username = questionary.text("Username:", style=custom_style).ask()
    if not username:
        return
        
    password = questionary.password("Password:", style=custom_style).ask()
    if not password:
        return
    
    with console.status(f"[cyan]Registering user {username}...", spinner="dots"):
        try:
            response = requests.post(f"{API_BASE_URL}/auth/register", json={
                "username": username,
                "password": password
            })
            
            data, success = handle_response(response)
            if success:
                console.print(f"{ICONS['success']} Registration successful!", style="bold green")
                console.print(f"User ID: {data.get('user_id', 'N/A')}", style="green")
                
                if questionary.confirm("Would you like to login now?", style=custom_style).ask():
                    login(username=username, password=password)
        except Exception as e:
            console.print(f"{ICONS['error']} Registration failed: {str(e)}", style="bold red")

def login(username=None, password=None):
    """Login and save the token"""
    if not username:
        console.print(Panel(f"{ICONS['login']} Login to Your Account", border_style="cyan", expand=False))
        username = questionary.text("Username:", style=custom_style).ask()
        if not username:
            return
            
    if not password:
        password = questionary.password("Password:", style=custom_style).ask()
        if not password:
            return
    
    with console.status(f"[cyan]Logging in as {username}...", spinner="dots"):
        try:
            response = requests.post(f"{API_BASE_URL}/auth/login", json={
                "username": username,
                "password": password
            })
            
            data, success = handle_response(response)
            if success:
                config = load_config()
                config['token'] = data.get('token')
                config['username'] = username
                config['user_id'] = data.get('user_id')
                save_config(config)
                console.print(f"{ICONS['success']} Login successful!", style="bold green")
        except Exception as e:
            console.print(f"{ICONS['error']} Login failed: {str(e)}", style="bold red")

def logout():
    """Logout and remove the token"""
    config = load_config()
    token = config.get('token')
    
    if not token:
        console.print(f"{ICONS['warning']} You are not logged in.", style="bold yellow")
        return
    
    with console.status("[cyan]Logging out...", spinner="dots"):
        try:
            headers = get_auth_header(config)
            response = requests.post(f"{API_BASE_URL}/auth/logout", headers=headers)
            
            # Whether the logout API call succeeds or not, we remove the token
            config.pop('token', None)
            save_config(config)
            
            console.print(f"{ICONS['success']} Logged out successfully!", style="bold green")
        except Exception as e:
            # Even if the API call fails, we still remove the token locally
            config.pop('token', None)
            save_config(config)
            console.print(f"{ICONS['warning']} Error during logout: {str(e)}", style="bold yellow")
            console.print("Local session cleared.", style="green")

def view_profile():
    """Show the current user's profile"""
    config = check_login_or_exit()
    headers = get_auth_header(config)
    
    with console.status("[cyan]Loading profile...", spinner="dots"):
        try:
            response = requests.get(f"{API_BASE_URL}/profiles/me", headers=headers)
            
            data, success = handle_response(response)
            if success:
                # Display profile if it exists
                cat_id = data.get('cat_id', 'None')
                cat_emoji = "😺" if cat_id == 0 else "😸" if cat_id == 1 else "😻" if cat_id == 10 else "🐱"
                
                # Get illness information
                illness_id = data.get('illness_id', 0)
                illness_name = data.get('illness_name', 'None')
                illness_name_ua = data.get('illness_name_ua', 'Немає')
                
                console.print(Panel(
                    f"[bold]Name:[/bold] {data.get('name', 'Not set')}\n"
                    f"[bold]About:[/bold] {data.get('about', 'Not set')}\n"
                    f"[bold]Cat:[/bold] {cat_emoji} (ID: {cat_id})\n"
                    f"[bold]Accessibility Needs:[/bold] {illness_name} ({illness_name_ua}) [ID: {illness_id}]",
                    title=f"{ICONS['cat']} Your Profile",
                    border_style="cyan",
                    expand=False
                ))
            elif response.status_code == 404:
                console.print(Panel("You don't have a profile yet. Use 'Update Profile' to create one.",
                            title=f"{ICONS['warning']} Profile Not Found",
                            border_style="yellow",
                            expand=False))
        except Exception as e:
            console.print(f"{ICONS['error']} Error getting profile: {str(e)}", style="bold red")

def update_profile():
    """Create or update the user's profile"""
    config = check_login_or_exit()
    headers = get_auth_header(config)
    
    console.print(Panel(f"{ICONS['cat']} Update Your Profile", border_style="cyan", expand=False))
    
    name = questionary.text("Name:", style=custom_style).ask()
    if not name:
        return
        
    about = questionary.text("About:", style=custom_style).ask()
    if not about:
        return
    
    cat_id = questionary.select(
        "Select your cat avatar:",
        choices=[
            {"name": "😺 Regular Cat (ID: 0)", "value": 0},
            {"name": "😸 Grinning Cat (ID: 1)", "value": 1},
            {"name": "😻 Heart Eyes Cat (ID: 10)", "value": 10}
        ],
        style=custom_style
    ).ask()
    
    if cat_id is None:
        return
    
    # Add illness selection
    illness_id = questionary.select(
        "Select your accessibility needs:",
        choices=[
            {"name": "None (Немає)", "value": 0},
            {"name": "Dyslexia (Дислексія)", "value": 1},
            {"name": "Cerebral Palsy - Motor Impairment (ДЦП - порушення моторики)", "value": 2},
            {"name": "Photosensitivity (Світлочутливість)", "value": 3},
            {"name": "Epilepsy (Епілепсія)", "value": 4},
            {"name": "Color Blindness (Дальтонізм)", "value": 5}
        ],
        style=custom_style
    ).ask()
    
    if illness_id is None:
        return
    
    with console.status("[cyan]Updating profile...", spinner="dots"):
        try:
            response = requests.post(f"{API_BASE_URL}/profiles", json={
                "name": name,
                "about": about,
                "cat_id": cat_id,
                "illness_id": illness_id
            }, headers=headers)
            
            data, success = handle_response(response)
            if success:
                console.print(f"{ICONS['success']} Profile updated successfully!", style="bold green")
        except Exception as e:
            console.print(f"{ICONS['error']} Error updating profile: {str(e)}", style="bold red")

def list_lessons():
    """List all lessons"""
    with console.status(f"[cyan]Loading lessons...", spinner="dots"):
        try:
            response = requests.get(f"{API_BASE_URL}/lessons")
            
            data, success = handle_response(response)
            if success:
                lessons = data.get('lessons', [])
                count = data.get('count', 0)
                
                if count == 0:
                    console.print(f"{ICONS['warning']} No lessons found.", style="bold yellow")
                    return
                
                # Create a table to display lessons
                table = Table(title=f"{ICONS['lesson']} Lessons ({count})")
                table.add_column("ID", style="cyan")
                table.add_column("Title", style="green")
                table.add_column("Course", style="blue")
                
                for lesson in lessons:
                    table.add_row(
                        lesson.get('id', 'N/A'),
                        lesson.get('title', 'N/A'),
                        lesson.get('course_id', 'N/A')
                    )
                
                console.print(table)
        except Exception as e:
            console.print(f"{ICONS['error']} Error listing lessons: {str(e)}", style="bold red")

def search_lessons():
    """Search for lessons"""
    query = questionary.text("Search query:", style=custom_style).ask()
    if not query:
        return
    
    with console.status(f"[cyan]Searching for '{query}'...", spinner="dots"):
        try:
            response = requests.get(f"{API_BASE_URL}/lessons/search?q={query}")
            
            data, success = handle_response(response)
            if success:
                results = data.get('results', [])
                count = data.get('count', 0)
                
                if count == 0:
                    console.print(f"{ICONS['info']} No lessons found matching '{query}'.", style="bold yellow")
                    return
                
                # Create a table to display search results
                table = Table(title=f"{ICONS['search']} Search Results for '{query}' ({count})")
                table.add_column("ID", style="cyan")
                table.add_column("Title", style="green")
                table.add_column("Course", style="blue")
                
                for lesson in results:
                    table.add_row(
                        lesson.get('id', 'N/A'),
                        lesson.get('title', 'N/A'),
                        lesson.get('course_id', 'N/A')
                    )
                
                console.print(table)
        except Exception as e:
            console.print(f"{ICONS['error']} Error searching lessons: {str(e)}", style="bold red")

def view_lesson_details():
    """View details for a specific lesson"""
    lesson_id = questionary.text("Lesson ID:", style=custom_style).ask()
    if not lesson_id:
        return
    
    with console.status(f"[cyan]Loading lesson details...", spinner="dots"):
        try:
            response = requests.get(f"{API_BASE_URL}/lessons/{lesson_id}")
            
            data, success = handle_response(response)
            if success:
                console.print(Panel(
                    f"[bold]Title:[/bold] {data.get('title', 'N/A')}\n"
                    f"[bold]ID:[/bold] {data.get('id', 'N/A')}\n"
                    f"[bold]Course:[/bold] {data.get('course_id', 'N/A')}\n"
                    + (f"[bold]YouTube Link:[/bold] {data.get('youtube_link')}" if 'youtube_link' in data else ""),
                    title=f"{ICONS['lesson']} Lesson Details",
                    border_style="cyan",
                    expand=False
                ))
        except Exception as e:
            console.print(f"{ICONS['error']} Error getting lesson details: {str(e)}", style="bold red")

def add_new_lesson():
    """Add a new lesson"""
    config = check_login_or_exit()
    headers = get_auth_header(config)
    
    console.print(Panel(f"{ICONS['lesson']} Add New Lesson", border_style="cyan", expand=False))
    
    lesson_id = questionary.text("Lesson ID:", style=custom_style).ask()
    if not lesson_id:
        return
        
    title = questionary.text("Title:", style=custom_style).ask()
    if not title:
        return
        
    course_id = questionary.text("Course ID:", style=custom_style).ask()
    if not course_id:
        return
        
    youtube_link = questionary.text("YouTube Link (optional):", style=custom_style).ask()
    
    lesson_data = {
        "id": lesson_id,
        "title": title,
        "course_id": course_id
    }
    
    if youtube_link:
        lesson_data["youtube_link"] = youtube_link
    
    with console.status("[cyan]Adding lesson...", spinner="dots"):
        try:
            response = requests.post(f"{API_BASE_URL}/lessons", json=lesson_data, headers=headers)
            
            data, success = handle_response(response)
            if success:
                console.print(f"{ICONS['success']} Lesson added successfully!", style="bold green")
        except Exception as e:
            console.print(f"{ICONS['error']} Error adding lesson: {str(e)}", style="bold red")

def generate_lesson_summary():
    """Generate a summary (conspect) for a lesson"""
    config = check_login_or_exit()
    headers = get_auth_header(config)
    
    lesson_id = questionary.text("Lesson ID:", style=custom_style).ask()
    if not lesson_id:
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Generating summary... This may take a while..."),
        transient=True
    ) as progress:
        task = progress.add_task("Generating...", total=None)
        
        try:
            response = requests.get(f"{API_BASE_URL}/lessons/{lesson_id}/conspect", headers=headers)
            
            data, success = handle_response(response)
            if success:
                console.print(Panel(
                    f"[bold]Title:[/bold] {data.get('title', 'N/A')}\n"
                    f"[bold]Course:[/bold] {data.get('course_id', 'N/A')}",
                    title=f"{ICONS['conspect']} Summary for Lesson {lesson_id}",
                    border_style="cyan",
                    expand=False
                ))
                
                # Display the conspect as Markdown
                conspect_text = data.get('conspect', 'No summary available.')
                console.print(Markdown(conspect_text))
                
                # Option to save to file
                if questionary.confirm("Save summary to file?", style=custom_style).ask():
                    filename = f"conspect_{lesson_id}.md"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(conspect_text)
                    console.print(f"{ICONS['success']} Summary saved to {filename}", style="bold green")
        except Exception as e:
            console.print(f"{ICONS['error']} Error generating summary: {str(e)}", style="bold red")

def generate_course_test():
    """Generate a test for a course"""
    config = check_login_or_exit()
    headers = get_auth_header(config)
    
    course_id = questionary.text("Course ID:", style=custom_style).ask()
    if not course_id:
        return
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]Generating test... This may take a while..."),
        transient=True
    ) as progress:
        task = progress.add_task("Generating...", total=None)
        
        try:
            response = requests.get(f"{API_BASE_URL}/courses/{course_id}/test", headers=headers)
            
            data, success = handle_response(response)
            if success:
                console.print(Panel(
                    f"[bold]Course:[/bold] {data.get('course_id', 'N/A')}\n"
                    f"[bold]Questions:[/bold] {len(data.get('questions', []))}\n"
                    f"[bold]Generated:[/bold] {data.get('timestamp', 'N/A')}",
                    title=f"{ICONS['test']} Test for Course {course_id}",
                    border_style="cyan",
                    expand=False
                ))
                
                # Display the questions
                questions = data.get('questions', [])
                for i, q in enumerate(questions, 1):
                    question_panel = Panel(
                        f"{q.get('question')}\n\n" + 
                        "\n".join([
                            f"{'[green]✓[/green] ' if j == q.get('correct_answer') else '  '}{chr(65+j)}. {option}"
                            for j, option in enumerate(q.get('options', []))
                        ]),
                        title=f"Question {i}",
                        border_style="blue",
                        expand=False
                    )
                    console.print(question_panel)
                
                # Option to save to file
                if questionary.confirm("Save test to file?", style=custom_style).ask():
                    filename = f"test_{course_id}.json"
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    console.print(f"{ICONS['success']} Test saved to {filename}", style="bold green")
        except Exception as e:
            console.print(f"{ICONS['error']} Error generating test: {str(e)}", style="bold red")

def text_to_speech():
    """Convert text to speech using the API"""
    console.print(Panel(f"{ICONS['tts']} Text to Speech", border_style="cyan", expand=False))
    
    # Get text from user
    text = questionary.text("Enter text to convert to speech:", style=custom_style).ask()
    if not text:
        return
    
    # Get language (default to Ukrainian)
    language_choices = [
        {"name": "Ukrainian (uk)", "value": "uk"},
        {"name": "English (en)", "value": "en"},
        {"name": "German (de)", "value": "de"},
        {"name": "French (fr)", "value": "fr"},
        {"name": "Spanish (es)", "value": "es"},
    ]
    
    lang = questionary.select("Select language:", choices=language_choices, style=custom_style).ask()
    if not lang:
        return
    
    with console.status(f"[cyan]Converting text to speech...", spinner="dots"):
        try:
            # Record start time
            start_time = time.time()
            
            # Make API request
            response = requests.post(f"{API_BASE_URL}/speech/tts", json={
                "text": text,
                "lang": lang
            })
            
            # Calculate duration
            api_duration = time.time() - start_time
            
            data, success = handle_response(response)
            if success:
                console.print(f"{ICONS['success']} Text successfully converted to speech!", style="bold green")
                
                # Update usage statistics
                update_usage_stats(
                    cost=0.005,  # Estimated cost per TTS request
                    api_duration=api_duration,
                    wall_duration=api_duration,
                    tts_requests=1,
                    tts_characters=len(text)
                )
                
                # Save audio to file
                audio_data = base64.b64decode(data.get('audio'))
                
                # Get filename from user
                filename = questionary.text(
                    "Enter filename to save audio (leave empty to play only):",
                    style=custom_style
                ).ask()
                
                # Create a temporary file if the user doesn't specify a filename
                temp_file = None
                if not filename:
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
                    filename = temp_file.name
                    temp_file.close()
                
                # Write audio data to file
                with open(filename, 'wb') as f:
                    f.write(audio_data)
                
                # Ask if the user wants to play the audio
                if questionary.confirm("Play the audio now?", style=custom_style).ask():
                    try:
                        # Try to play the audio using the system's default player
                        if sys.platform == 'win32':
                            os.system(f'start {filename}')
                        elif sys.platform == 'darwin':
                            os.system(f'open {filename}')
                        else:
                            os.system(f'xdg-open {filename}')
                        
                        console.print(f"{ICONS['info']} Playing audio...", style="bold blue")
                        # Give some time for the player to start
                        time.sleep(1)
                    except Exception as e:
                        console.print(f"{ICONS['error']} Error playing audio: {str(e)}", style="bold red")
                
                # Clean up temp file if used
                if temp_file:
                    try:
                        os.unlink(filename)
                    except:
                        pass
                
        except Exception as e:
            console.print(f"{ICONS['error']} Error converting text to speech: {str(e)}", style="bold red")

def update_usage_stats(cost=0.0, api_duration=0.0, wall_duration=0.0, tts_requests=0, 
                       stt_requests=0, tts_characters=0, stt_seconds=0, lines_added=0, lines_removed=0):
    """Update usage statistics with new information"""
    cost_file = os.path.join(CONFIG_DIR, "usage_stats.json")
    ensure_config_dir()
    
    # Load existing stats or create new ones
    if os.path.exists(cost_file):
        with open(cost_file, 'r') as f:
            usage_stats = json.load(f)
    else:
        usage_stats = {
            "total_cost": 0.0,
            "api_duration_seconds": 0.0,
            "wall_duration_seconds": 0.0,
            "tts_requests": 0,
            "stt_requests": 0,
            "tts_characters": 0,
            "stt_seconds": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "last_updated": datetime.datetime.now().isoformat()
        }
    
    # Update the stats
    usage_stats["total_cost"] += cost
    usage_stats["api_duration_seconds"] += api_duration
    usage_stats["wall_duration_seconds"] += wall_duration
    usage_stats["tts_requests"] += tts_requests
    usage_stats["stt_requests"] += stt_requests
    usage_stats["tts_characters"] += tts_characters
    usage_stats["stt_seconds"] += stt_seconds
    usage_stats["lines_added"] += lines_added
    usage_stats["lines_removed"] += lines_removed
    usage_stats["last_updated"] = datetime.datetime.now().isoformat()
    
    # Save the updated stats
    with open(cost_file, 'w') as f:
        json.dump(usage_stats, f, indent=2)

def speech_to_text():
    """Convert speech to text using the API"""
    console.print(Panel(f"{ICONS['stt']} Speech to Text", border_style="cyan", expand=False))
    
    # Ask whether to record new audio or use existing file
    input_choices = [
        {"name": "Record new audio", "value": "record"},
        {"name": "Use existing audio file", "value": "file"}
    ]
    
    input_type = questionary.select("How would you like to input speech?", choices=input_choices, style=custom_style).ask()
    if not input_type:
        return
    
    audio_data = None
    
    if input_type == "record":
        # Record audio
        console.print(f"{ICONS['info']} Recording audio...", style="bold blue")
        console.print("Press Enter to start recording and press it again to stop.", style="blue")
        
        # Wait for user to press Enter to start
        questionary.text("", style=custom_style).ask()
        
        try:
            # Audio recording parameters
            FORMAT = pyaudio.paInt16
            CHANNELS = 1
            RATE = 16000
            CHUNK = 1024
            
            # Create a temporary file for the recording
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                filename = temp_file.name
            
            # Start recording
            console.print("Recording... Press Enter to stop.", style="bold red")
            
            # Initialize PyAudio
            audio = pyaudio.PyAudio()
            
            # Open stream
            stream = audio.open(format=FORMAT, channels=CHANNELS,
                              rate=RATE, input=True,
                              frames_per_buffer=CHUNK)
            
            frames = []
            recording = True
            
            # Start a thread to wait for Enter key
            def wait_for_enter():
                nonlocal recording
                input()  # Wait for Enter key
                recording = False
            
            import threading
            enter_thread = threading.Thread(target=wait_for_enter)
            enter_thread.daemon = True
            enter_thread.start()
            
            # Record until Enter is pressed
            while recording:
                data = stream.read(CHUNK)
                frames.append(data)
            
            # Stop and close the stream
            stream.stop_stream()
            stream.close()
            audio.terminate()
            
            console.print("Recording stopped.", style="green")
            
            # Save the recorded audio to wav file
            wf = wave.open(filename, 'wb')
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(audio.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()
            
            # Read the file
            with open(filename, 'rb') as f:
                audio_data = f.read()
            
            # Clean up temp file
            try:
                os.unlink(filename)
            except:
                pass
            
        except Exception as e:
            console.print(f"{ICONS['error']} Error recording audio: {str(e)}", style="bold red")
            return
    
    elif input_type == "file":
        # Get audio file path
        file_path = questionary.text("Enter path to audio file:", style=custom_style).ask()
        if not file_path:
            return
        
        try:
            # Read the file
            with open(file_path, 'rb') as f:
                audio_data = f.read()
        except Exception as e:
            console.print(f"{ICONS['error']} Error reading audio file: {str(e)}", style="bold red")
            return
    
    # Get language (default to Ukrainian)
    language_choices = [
        {"name": "Ukrainian (uk)", "value": "uk"},
        {"name": "English (en)", "value": "en"},
        {"name": "German (de)", "value": "de"},
        {"name": "French (fr)", "value": "fr"},
        {"name": "Spanish (es)", "value": "es"},
    ]
    
    lang = questionary.select("Select language:", choices=language_choices, style=custom_style).ask()
    if not lang:
        return
    
    with console.status(f"[cyan]Transcribing speech to text...", spinner="dots"):
        try:
            # Record start time
            start_time = time.time()
            
            # Encode audio data as base64
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Make API request
            response = requests.post(f"{API_BASE_URL}/speech/stt", json={
                "audio": audio_base64,
                "lang": lang
            })
            
            # Calculate duration
            api_duration = time.time() - start_time
            
            data, success = handle_response(response)
            if success:
                # Estimate audio duration in seconds (rough estimate based on file size)
                audio_duration = len(audio_data) / 16000 / 2  # Assuming 16kHz mono 16-bit audio
                
                # Update usage statistics
                update_usage_stats(
                    cost=0.015,  # Estimated cost per STT request
                    api_duration=api_duration,
                    wall_duration=api_duration,
                    stt_requests=1,
                    stt_seconds=audio_duration
                )
                
                # Display transcription
                console.print(Panel(
                    f"{data.get('text', 'No text transcribed.')}",
                    title=f"{ICONS['stt']} Transcription Result",
                    border_style="green",
                    expand=False
                ))
                
                # Option to save to file
                if questionary.confirm("Save transcription to file?", style=custom_style).ask():
                    filename = questionary.text("Enter filename:", style=custom_style).ask() or "transcription.txt"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(data.get('text', ''))
                    console.print(f"{ICONS['success']} Transcription saved to {filename}", style="bold green")
                
        except Exception as e:
            console.print(f"{ICONS['error']} Error converting speech to text: {str(e)}", style="bold red")

def show_usage_cost():
    """Show API usage cost and statistics"""
    console.print(Panel(f"{ICONS['cost']} Usage Cost and Statistics", border_style="cyan", expand=False))
    
    # Check if the usage file exists
    cost_file = os.path.join(CONFIG_DIR, "usage_stats.json")
    
    if not os.path.exists(cost_file):
        # Initialize with default values if not exists
        usage_stats = {
            "total_cost": 0.0,
            "api_duration_seconds": 0.0,
            "wall_duration_seconds": 0.0,
            "tts_requests": 0,
            "stt_requests": 0,
            "tts_characters": 0,
            "stt_seconds": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "last_updated": datetime.datetime.now().isoformat()
        }
        ensure_config_dir()
        with open(cost_file, 'w') as f:
            json.dump(usage_stats, f, indent=2)
    else:
        # Load existing stats
        with open(cost_file, 'r') as f:
            usage_stats = json.load(f)
    
    # Format the times nicely
    api_duration_formatted = format_duration(usage_stats.get("api_duration_seconds", 0))
    wall_duration_formatted = format_duration(usage_stats.get("wall_duration_seconds", 0))
    
    # Create a table for the stats
    table = Table(title="Usage Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Cost", f"${usage_stats.get('total_cost', 0):.2f}")
    table.add_row("API Duration", api_duration_formatted)
    table.add_row("Wall Clock Duration", wall_duration_formatted)
    table.add_row("TTS Requests", str(usage_stats.get("tts_requests", 0)))
    table.add_row("STT Requests", str(usage_stats.get("stt_requests", 0)))
    table.add_row("TTS Characters Processed", str(usage_stats.get("tts_characters", 0)))
    table.add_row("STT Audio Seconds Processed", str(usage_stats.get("stt_seconds", 0)))
    table.add_row("Code Lines Added", str(usage_stats.get("lines_added", 0)))
    table.add_row("Code Lines Removed", str(usage_stats.get("lines_removed", 0)))
    table.add_row("Last Updated", usage_stats.get("last_updated", "Never"))
    
    console.print(table)
    
    # Ask if user wants to simulate adding usage
    if questionary.confirm("Would you like to simulate adding usage (for testing)?", style=custom_style).ask():
        # Update the stats with some simulated usage
        usage_stats["total_cost"] += 0.25
        usage_stats["api_duration_seconds"] += 60
        usage_stats["wall_duration_seconds"] += 120
        usage_stats["tts_requests"] += 1
        usage_stats["tts_characters"] += 200
        usage_stats["last_updated"] = datetime.datetime.now().isoformat()
        
        # Save the updated stats
        with open(cost_file, 'w') as f:
            json.dump(usage_stats, f, indent=2)
        
        console.print(f"{ICONS['success']} Usage statistics updated with simulated data", style="bold green")

def format_duration(seconds):
    """Format seconds into a readable duration string"""
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours > 0:
        return f"{int(hours)}h {int(minutes)}m {seconds:.1f}s"
    elif minutes > 0:
        return f"{int(minutes)}m {seconds:.1f}s"
    else:
        return f"{seconds:.1f}s"

def test_api_connection():
    """Test the connection to the API server"""
    with console.status("[cyan]Testing API connection...", spinner="dots"):
        try:
            response = requests.get(f"{API_BASE_URL}/test-openrouter")
            
            data, success = handle_response(response)
            if success and data.get('success', False):
                console.print(Panel(
                    "OpenRouter connection is working!",
                    title=f"{ICONS['success']} Connection Test",
                    border_style="green",
                    expand=False
                ))
            else:
                console.print(Panel(
                    f"Reason: {data.get('error', 'Unknown error')}",
                    title=f"{ICONS['warning']} Connection Failed",
                    border_style="yellow",
                    expand=False
                ))
        except Exception as e:
            console.print(Panel(
                f"Error: {str(e)}",
                title=f"{ICONS['error']} Connection Error",
                border_style="red",
                expand=False
            ))

def main():
    """Main entry point for the CLI"""
    # Clear the screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    while True:
        # Show dashboard
        show_dashboard()
        
        # Show menu and get choice
        choice = main_menu()
        
        # Clear the screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Process the choice
        if choice == "login":
            login()
        elif choice == "register":
            register()
        elif choice == "logout":
            logout()
        elif choice == "view_profile":
            view_profile()
        elif choice == "update_profile":
            update_profile()
        elif choice == "list_lessons":
            list_lessons()
        elif choice == "search_lessons":
            search_lessons()
        elif choice == "view_lesson_details":
            view_lesson_details()
        elif choice == "add_new_lesson":
            add_new_lesson()
        elif choice == "generate_lesson_summary":
            generate_lesson_summary()
        elif choice == "generate_course_test":
            generate_course_test()
        elif choice == "test_api_connection":
            test_api_connection()
        elif choice == "show_usage_cost":
            show_usage_cost()
        elif choice == "text_to_speech":
            text_to_speech()
        elif choice == "speech_to_text":
            speech_to_text()
        
        # Pause to allow user to read output
        console.print()
        questionary.text("Press Enter to continue...", style=custom_style).ask()
        
        # Clear the screen for the next loop
        os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n\n{ICONS['info']} Operation cancelled by user.", style="bold blue")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n{ICONS['error']} Unexpected error: {str(e)}", style="bold red")
        sys.exit(1)
