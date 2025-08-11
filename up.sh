#!/bin/bash

# up.sh - Django development server launcher for containers
# Handles both devcontainer and normal development container environments

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Find Artek Django Development Server${NC}"

# Function to detect if we're in devcontainer vs normal container
detect_environment() {
    if [ -d "/workspace" ] && [ -f "/workspace/app-main/manage.py" ]; then
        echo "devcontainer"
    elif [ -d "/app" ] && [ -f "/app/manage.py" ]; then
        echo "docker"
    else
        echo "unknown"
    fi
}

# Function to start development server in devcontainer
start_devcontainer() {
    echo -e "${GREEN}📦 Detected: VS Code Dev Container environment${NC}"
    
    # Navigate to Django project directory
    cd /workspace/app-main
    
    echo -e "${GREEN}🌐 Starting Django development server on 0.0.0.0:8099${NC}"
    echo -e "${BLUE}🔗 Access your app at: http://localhost:8100${NC}"
    echo -e "${YELLOW}📝 Note: Port 8099 (container) is mapped to 8100 (host) in devcontainer${NC}"
    echo ""
    
    # Start the development server
    exec python manage.py runserver 0.0.0.0:8099 --settings find_artek.development_settings
}

# Function to start development server in normal docker container
start_docker() {
    echo -e "${GREEN}🐳 Detected: Docker container environment${NC}"
    
    # Navigate to Django project directory
    cd /app
    
    echo -e "${GREEN}🌐 Starting Django development server on 0.0.0.0:8099${NC}"
    echo -e "${BLUE}🔗 Access your app at: http://localhost:8098${NC}"
    echo ""
    
    # Start the development server
    exec python manage.py runserver 0.0.0.0:8099 --settings find_artek.development_settings
}

# Main execution
main() {
    ENV=$(detect_environment)
    
    echo -e "${YELLOW}� Environment: $ENV${NC}"
    echo ""
    
    case $ENV in
        "devcontainer")
            start_devcontainer
            ;;
        "docker")
            start_docker
            ;;
        *)
            echo -e "${RED}❌ Error: Cannot detect Django project location${NC}"
            echo -e "${YELLOW}💡 Expected to find manage.py in either:${NC}"
            echo -e "${YELLOW}   - /workspace/app-main/manage.py (devcontainer)${NC}"
            echo -e "${YELLOW}   - /app/manage.py (docker container)${NC}"
            exit 1
            ;;
    esac
}

# Check for help flag
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "up.sh - Django development server launcher for containers"
    echo ""
    echo "Usage: ./up.sh"
    echo ""
    echo "This script automatically detects your container environment and starts"
    echo "the Django development server appropriately:"
    echo ""
    echo "  🔹 VS Code devcontainer: Starts Django from /workspace/app-main"
    echo "  🔹 Docker container: Starts Django from /app"
    echo ""
    echo "No arguments are required - the script handles everything automatically."
    exit 0
fi

# Run main function
main "$@"
