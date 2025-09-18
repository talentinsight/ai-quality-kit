#!/usr/bin/env python3
"""
Smart requirements.txt updater that organizes packages by category
and keeps only the main packages needed for the project.
"""

import subprocess
import sys
import os
from pathlib import Path

# Main package categories and their key packages
MAIN_PACKAGES = {
    "Core FastAPI and web framework": [
        "fastapi", "uvicorn", "pydantic", "pydantic-core", "starlette"
    ],
    "HTTP and async": [
        "httpx", "aiohttp", "requests", "httpcore"
    ],
    "Environment and configuration": [
        "python-dotenv"
    ],
    "AI/ML Libraries": [
        "openai", "anthropic", "langchain", "langchain-openai", 
        "langchain-community", "langchain-core", "langchain-google-genai",
        "langchain-text-splitters", "langsmith"
    ],
    "Vector search and ML": [
        "scikit-learn", "scipy", "numpy", "joblib", "threadpoolctl"
    ],
    "RAG Evaluation": [
        "ragas", "datasets", "instructor"
    ],
    "Database and caching": [
        "snowflake-connector-python", "redis", "upstash-redis"
    ],
    "Authentication and security": [
        "pyjwt", "cryptography", "passlib", "msal", "pyOpenSSL"
    ],
    "Data processing and utilities": [
        "pandas", "pyyaml", "jsonschema", "python-multipart", 
        "jinja2", "openpyxl"
    ],
    "Testing and quality": [
        "pytest", "pytest-asyncio", "pytest-cov", "pytest-mock", "coverage"
    ],
    "Development tools": [
        "black", "flake8", "mypy"
    ],
    "Date and time utilities": [
        "python-dateutil", "pytz", "tzdata"
    ],
    "Text processing": [
        "beautifulsoup4", "lxml"
    ],
    "Monitoring and observability": [
        "structlog", "prometheus_client"
    ],
    "Type hints": [
        "typing-extensions", "typing-inspect", "typing-inspection"
    ],
    "Utilities": [
        "click", "tqdm", "rich", "tenacity"
    ]
}

def get_installed_packages():
    """Get list of installed packages with versions."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            capture_output=True, text=True, check=True
        )
        packages = {}
        for line in result.stdout.strip().split('\n'):
            if '==' in line:
                name, version = line.split('==', 1)
                packages[name.lower()] = f"{name}=={version}"
        return packages
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running pip freeze: {e}")
        return {}

def create_organized_requirements(installed_packages):
    """Create organized requirements.txt content."""
    content = []
    
    for category, package_names in MAIN_PACKAGES.items():
        content.append(f"# {category}")
        
        for package_name in package_names:
            package_key = package_name.lower()
            if package_key in installed_packages:
                content.append(installed_packages[package_key])
            else:
                print(f"⚠️  Warning: {package_name} not found in installed packages")
        
        content.append("")  # Empty line between categories
    
    return "\n".join(content)

def main():
    """Main function."""
    print("🔄 Smart requirements.txt updater")
    
    # Check if virtual environment is activated
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("❌ Virtual environment not detected. Please activate .venv first.")
        sys.exit(1)
    
    # Check if we're in the right directory
    if not Path("requirements.txt").exists():
        print("❌ requirements.txt not found. Please run this script from the project root.")
        sys.exit(1)
    
    # Create backup
    backup_name = f"requirements.txt.backup.{int(os.getpid())}"
    try:
        with open("requirements.txt", "r") as f:
            current_content = f.read()
        
        with open(backup_name, "w") as f:
            f.write(current_content)
        print(f"📋 Created backup: {backup_name}")
    except Exception as e:
        print(f"⚠️  Warning: Could not create backup: {e}")
    
    # Get installed packages
    print("📦 Getting installed packages...")
    installed_packages = get_installed_packages()
    
    if not installed_packages:
        print("❌ No packages found. Exiting.")
        sys.exit(1)
    
    # Create organized requirements
    print("🔧 Organizing packages by category...")
    new_content = create_organized_requirements(installed_packages)
    
    # Write new requirements.txt
    try:
        with open("requirements.txt", "w") as f:
            f.write(new_content)
        print("✅ requirements.txt updated successfully!")
        
        # Count packages
        package_count = len([line for line in new_content.split('\n') if '==' in line])
        print(f"📊 Total packages: {package_count}")
        
    except Exception as e:
        print(f"❌ Error writing requirements.txt: {e}")
        sys.exit(1)
    
    print("🎉 Done! requirements.txt has been updated with organized package categories.")
    print("💡 Tip: Review the file and remove any packages that aren't needed for production.")

if __name__ == "__main__":
    main()
