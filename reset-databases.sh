#!/bin/bash

# Script to reset Matrix database volumes
# WARNING: This will permanently delete all database data!

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print colored output
print_warning() {
    echo -e "${YELLOW}WARNING: $1${NC}"
}

print_error() {
    echo -e "${RED}ERROR: $1${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_info() {
    echo -e "$1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if we have docker permissions
check_docker_permissions() {
    if ! docker ps >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

# Function to run docker command with sudo if needed
run_docker_cmd() {
    if check_docker_permissions; then
        "$@"
    else
        print_warning "Docker requires elevated permissions. Running with sudo..."
        sudo "$@"
    fi
}

# Function to run docker-compose command with sudo if needed
run_compose_cmd() {
    if check_docker_permissions; then
        docker-compose "$@"
    else
        print_warning "Docker requires elevated permissions. Running with sudo..."
        sudo docker-compose "$@"
    fi
}

echo "=========================================="
echo "Matrix Database Reset Script"
echo "=========================================="
echo

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found in current directory!"
    echo "Please run this script from your Matrix server directory."
    exit 1
fi

# Check if required commands exist
if ! command_exists docker; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed or not in PATH"
    echo "You may need to install docker-compose or use 'docker compose' instead."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1 && ! sudo docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running"
    echo "Please start Docker and try again."
    exit 1
fi

print_warning "This script will permanently delete ALL Matrix database data!"
echo
echo "What this script will do:"
echo "  1. Stop all Matrix services"
echo "  2. Remove PostgreSQL database volume (postgres_data)"
echo "  3. Remove Valkey/Redis cache volume (valkey_data)"
echo "  4. Remove any associated data"
echo
echo "This means you will lose:"
echo "  • All user accounts and profiles"
echo "  • All chat rooms and messages"
echo "  • All media files and uploads"
echo "  • All server state and cache"
echo
print_warning "This action CANNOT be undone!"
echo

# Double confirmation
echo "Type 'DELETE ALL DATA' to confirm you want to proceed:"
read -r confirmation

if [ "$confirmation" != "DELETE ALL DATA" ]; then
    echo "Operation cancelled."
    exit 0
fi

echo
print_warning "Last chance! Press Enter to continue or Ctrl+C to abort..."
read -r

echo
print_info "Starting database reset process..."

# Step 1: Stop all services
echo
print_info "Step 1: Stopping Matrix services..."
if run_compose_cmd ps -q | grep -q .; then
    print_info "Services are running, stopping them..."
    run_compose_cmd down
    print_success "Services stopped"
else
    print_info "No services were running"
fi

# Wait a moment for containers to fully stop
sleep 2

# Step 2: Remove volumes
echo
print_info "Step 2: Removing database volumes..."

# Get the project name (directory name by default)
PROJECT_NAME=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')

# List of volumes to remove
VOLUMES=(
    "${PROJECT_NAME}_postgres_data"
    "${PROJECT_NAME}_valkey_data"
)

for volume in "${VOLUMES[@]}"; do
    if run_docker_cmd volume ls -q | grep -q "^${volume}$"; then
        print_info "Removing volume: $volume"
        if run_docker_cmd volume rm "$volume"; then
            print_success "Removed volume: $volume"
        else
            print_error "Failed to remove volume: $volume"
            echo "You may need to stop any remaining containers using this volume."
            exit 1
        fi
    else
        print_info "Volume $volume does not exist (already clean)"
    fi
done

# Step 3: Clean up any orphaned containers
echo
print_info "Step 3: Cleaning up any orphaned containers..."
if run_docker_cmd container ls -a --filter "label=com.docker.compose.project=${PROJECT_NAME}" -q | grep -q .; then
    print_info "Removing orphaned containers..."
    run_docker_cmd container ls -a --filter "label=com.docker.compose.project=${PROJECT_NAME}" -q | xargs run_docker_cmd container rm -f
    print_success "Orphaned containers removed"
else
    print_info "No orphaned containers found"
fi

# Step 4: Clean up any orphaned networks
echo
print_info "Step 4: Cleaning up networks..."
NETWORK_NAME="${PROJECT_NAME}_matrix_network"
if run_docker_cmd network ls --filter "name=${NETWORK_NAME}" -q | grep -q .; then
    print_info "Removing network: $NETWORK_NAME"
    run_docker_cmd network rm "$NETWORK_NAME" 2>/dev/null || print_info "Network removal not needed"
fi

echo
print_success "Database reset completed successfully!"
echo
echo "=========================================="
echo "Next Steps:"
echo "=========================================="
echo
echo "1. Verify your configuration files have the correct secrets:"
echo "   • Check docker-compose.yml for POSTGRES_PASSWORD"
echo "   • Check homeserver.yaml for database password match"
echo "   • Ensure all placeholders are replaced with actual values"
echo
echo "2. Start your Matrix server:"
echo "   docker-compose up -d"
echo
echo "3. Wait for services to initialize (this may take a few minutes)"
echo
echo "4. Create your admin user:"
echo "   docker-compose exec synapse register_new_matrix_user -c /data/homeserver.yaml http://localhost:8008"
echo
echo "5. Generate admin token and update .env file"
echo
echo "6. Test your installation:"
echo "   curl https://matrix.yourdomain.com/_matrix/client/versions"
echo
print_warning "Remember: All previous data has been permanently deleted."
print_info "Your Matrix server will start fresh with the new configuration."
