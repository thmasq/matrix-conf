#!/bin/bash

# Script to reset Matrix database volumes
# WARNING: This will permanently delete all database data!

set -e

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Global variable to track if we've already shown the sudo warning
SUDO_WARNING_SHOWN=false

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
        docker "$@"
    else
        if [ "$SUDO_WARNING_SHOWN" = false ]; then
            print_warning "Docker requires elevated permissions. Using sudo for remaining commands..."
            SUDO_WARNING_SHOWN=true
        fi
        sudo docker "$@"
    fi
}

# Function to run docker-compose command with sudo if needed
run_compose_cmd() {
    if check_docker_permissions; then
        docker-compose "$@"
    else
        if [ "$SUDO_WARNING_SHOWN" = false ]; then
            print_warning "Docker requires elevated permissions. Using sudo for remaining commands..."
            SUDO_WARNING_SHOWN=true
        fi
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

# Get the project name (directory name by default, keeping dashes)
PROJECT_NAME=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]')

# List of volumes to remove
VOLUMES=(
    "${PROJECT_NAME}_postgres_data"
    "${PROJECT_NAME}_valkey_data"
)

echo "=========================================="
echo "Volume Detection"
echo "=========================================="
echo

print_info "Scanning for volumes with project name: $PROJECT_NAME"
echo

# Check what volumes actually exist
print_info "Matrix-related volumes found on system:"
EXISTING_VOLUMES=$(run_docker_cmd volume ls --format "{{.Name}}" | grep -E "(postgres|valkey)" || true)

if [ -n "$EXISTING_VOLUMES" ]; then
    echo "$EXISTING_VOLUMES" | while read -r volume; do
        if [ -n "$volume" ]; then
            echo "  • $volume"
        fi
    done
else
    print_info "  No postgres/valkey volumes found on system"
fi

echo

# Check which of our expected volumes exist
print_info "Volumes that will be targeted for deletion:"
VOLUMES_TO_DELETE=()
for volume in "${VOLUMES[@]}"; do
    if run_docker_cmd volume ls -q | grep -q "^${volume}$"; then
        echo "  ✓ $volume (exists - will be deleted)"
        VOLUMES_TO_DELETE+=("$volume")
    else
        echo "  ✗ $volume (doesn't exist - will be skipped)"
    fi
done

echo

if [ ${#VOLUMES_TO_DELETE[@]} -eq 0 ]; then
    print_info "No target volumes found to delete."
    echo "If you have Matrix volumes with different names, you may need to remove them manually."
    echo
    echo "To see all volumes: docker volume ls"
    echo "To remove a volume: docker volume rm VOLUME_NAME"
    exit 0
fi

print_warning "Found ${#VOLUMES_TO_DELETE[@]} volume(s) that will be permanently deleted!"

echo
echo "=========================================="
echo "Confirmation Required"
echo "=========================================="
echo

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

# Remove the volumes we found earlier
for volume in "${VOLUMES_TO_DELETE[@]}"; do
    print_info "Removing volume: $volume"
    if run_docker_cmd volume rm "$volume"; then
        print_success "Removed volume: $volume"
    else
        print_error "Failed to remove volume: $volume"
        echo "You may need to stop any remaining containers using this volume."
        exit 1
    fi
done

# Step 3: Clean up any orphaned containers
echo
print_info "Step 3: Cleaning up orphaned containers..."
ORPHANED_CONTAINERS=$(run_docker_cmd container ls -a --filter "label=com.docker.compose.project=${PROJECT_NAME}" -q)
if [ -n "$ORPHANED_CONTAINERS" ]; then
    print_info "Found orphaned containers, removing..."
    echo "$ORPHANED_CONTAINERS" | while read -r container_id; do
        if [ -n "$container_id" ]; then
            run_docker_cmd container rm -f "$container_id"
        fi
    done
    print_success "Orphaned containers removed"
else
    print_info "No orphaned containers found"
fi

# Step 4: Clean up networks
echo
print_info "Step 4: Cleaning up networks..."
NETWORK_NAME="${PROJECT_NAME}_matrix_network"
if run_docker_cmd network ls --filter "name=${NETWORK_NAME}" -q | grep -q .; then
    print_info "Removing network: $NETWORK_NAME"
    run_docker_cmd network rm "$NETWORK_NAME" 2>/dev/null || print_info "Network already removed"
else
    print_info "No networks to clean up"
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
