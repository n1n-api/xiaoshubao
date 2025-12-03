import os
import sys

# Add the current directory to sys.path so that 'backend' can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app

app = create_app()

# This is required for Vercel to find the app instance
# Vercel looks for a variable named 'app' or 'application'

