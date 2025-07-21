#!/bin/bash

# Script to fix Matrix room permissions for Element Call
# This allows regular users to participate in video calls

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading configuration from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Validate required variables
if [ -z "$HOMESERVER_URL" ] || [ -z "$ADMIN_TOKEN" ]; then
    echo "Error: HOMESERVER_URL and ADMIN_TOKEN must be set"
    echo "Either set them as environment variables or create a .env file"
    echo "See .env.example for reference"
    exit 1
fi

echo "Using homeserver: $HOMESERVER_URL"

# Function to get room ID from room alias
get_room_id_from_alias() {
    local room_alias=$1
    # URL encode the room alias
    local encoded_alias=$(echo "$room_alias" | sed 's/#/%23/g' | sed 's/:/%3A/g')
    
    curl -s -X GET "${HOMESERVER_URL}/_matrix/client/r0/directory/room/${encoded_alias}" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | \
        jq -r '.room_id'
}

# Function to fix permissions in a specific room
fix_room_permissions() {
    local room_id=$1
    
    echo "Fixing permissions for room: $room_id"
    
    # Get current power levels
    current_power_levels=$(curl -s -X GET "${HOMESERVER_URL}/_matrix/client/v3/rooms/${room_id}/state/m.room.power_levels" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}")
    
    # Check if we got valid power levels
    if echo "$current_power_levels" | jq -e '.events' > /dev/null 2>&1; then
        echo "Current power levels retrieved successfully"
    else
        echo "Warning: Could not retrieve current power levels or room not found"
        echo "Response: $current_power_levels"
        return 1
    fi
    
    # Update power levels to allow MatrixRTC events at lower levels
    updated_power_levels=$(echo "$current_power_levels" | jq '
        .events = (.events // {}) |
        .events["org.matrix.msc3401.call.member"] = 0 |
        .events["org.matrix.msc3401.call"] = 0 |
        .events["m.call.member"] = 0 |
        .events["m.call"] = 0
    ')
    
    echo "Updating power levels to allow Element Call participation..."
    
    response=$(curl -s -X PUT "${HOMESERVER_URL}/_matrix/client/v3/rooms/${room_id}/state/m.room.power_levels" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "$updated_power_levels")
    
    # Check if update was successful
    if echo "$response" | jq -e '.event_id' > /dev/null 2>&1; then
        event_id=$(echo "$response" | jq -r '.event_id')
        echo "✓ Permissions updated successfully. Event ID: $event_id"
    else
        echo "✗ Error updating permissions. Response: $response"
        return 1
    fi
}

# Function to list all rooms (matching delete-room.sh format)
list_rooms() {
    echo "Listing all rooms on the server:"
    curl -s -X GET "${HOMESERVER_URL}/_synapse/admin/v1/rooms" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | \
        jq '.rooms[] | {room_id: .room_id, name: .name, alias: .canonical_alias, members: .joined_members}'
}

# Function to fix all rooms
fix_all_rooms() {
    echo "Fixing permissions for all rooms..."
    
    room_ids=$(curl -s -X GET "${HOMESERVER_URL}/_synapse/admin/v1/rooms" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | \
        jq -r '.rooms[].room_id')
    
    if [ -z "$room_ids" ]; then
        echo "No rooms found or error retrieving rooms"
        return 1
    fi
    
    total_rooms=$(echo "$room_ids" | wc -l)
    current=0
    success=0
    failed=0
    
    for room_id in $room_ids; do
        current=$((current + 1))
        echo "Processing room $current/$total_rooms: $room_id"
        
        if fix_room_permissions "$room_id"; then
            success=$((success + 1))
        else
            failed=$((failed + 1))
        fi
        echo "---"
    done
    
    echo "Summary:"
    echo "  Total rooms: $total_rooms"
    echo "  Successfully updated: $success"
    echo "  Failed: $failed"
}

# Function to check if room permissions are correctly set
check_room_permissions() {
    local room_id=$1
    
    echo "Checking permissions for room: $room_id"
    
    power_levels=$(curl -s -X GET "${HOMESERVER_URL}/_matrix/client/v3/rooms/${room_id}/state/m.room.power_levels" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}")
    
    if echo "$power_levels" | jq -e '.events' > /dev/null 2>&1; then
        echo "Power levels for MatrixRTC events:"
        echo "$power_levels" | jq -r '
            .events as $events |
            [
                "org.matrix.msc3401.call.member: \($events["org.matrix.msc3401.call.member"] // "not set")",
                "org.matrix.msc3401.call: \($events["org.matrix.msc3401.call"] // "not set")",
                "m.call.member: \($events["m.call.member"] // "not set")",
                "m.call: \($events["m.call"] // "not set")"
            ] | .[]
        '
    else
        echo "Error retrieving power levels: $power_levels"
        return 1
    fi
}

# Main script logic
case "$1" in
    "list")
        list_rooms
        ;;
    "fix")
        if [ -z "$2" ]; then
            echo "Usage: $0 fix <room_id_or_alias>"
            echo "Example: $0 fix '!roomid:matrix.tantalius.com'"
            echo "Example: $0 fix '#roomname:matrix.tantalius.com'"
            exit 1
        fi
        
        room_identifier="$2"
        
        # Check if it's a room alias (starts with #) or room ID (starts with !)
        if [[ "$room_identifier" == "#"* ]]; then
            echo "Getting room ID for alias: $room_identifier"
            room_id=$(get_room_id_from_alias "$room_identifier")
            if [ "$room_id" == "null" ] || [ -z "$room_id" ]; then
                echo "Error: Could not find room with alias $room_identifier"
                exit 1
            fi
            echo "Found room ID: $room_id"
        else
            room_id="$room_identifier"
        fi
        
        fix_room_permissions "$room_id"
        ;;
    "fix-all")
        fix_all_rooms
        ;;
    "check")
        if [ -z "$2" ]; then
            echo "Usage: $0 check <room_id_or_alias>"
            echo "Example: $0 check '!roomid:matrix.tantalius.com'"
            echo "Example: $0 check '#roomname:matrix.tantalius.com'"
            exit 1
        fi
        
        room_identifier="$2"
        
        # Check if it's a room alias (starts with #) or room ID (starts with !)
        if [[ "$room_identifier" == "#"* ]]; then
            echo "Getting room ID for alias: $room_identifier"
            room_id=$(get_room_id_from_alias "$room_identifier")
            if [ "$room_id" == "null" ] || [ -z "$room_id" ]; then
                echo "Error: Could not find room with alias $room_identifier"
                exit 1
            fi
            echo "Found room ID: $room_id"
        else
            room_id="$room_identifier"
        fi
        
        check_room_permissions "$room_id"
        ;;
    *)
        echo "Matrix Room Permissions Fix for Element Call"
        echo "Usage:"
        echo "  $0 list                         # List all rooms"
        echo "  $0 fix <room_id_or_alias>      # Fix permissions for specific room"
        echo "  $0 fix-all                     # Fix permissions for all rooms"
        echo "  $0 check <room_id_or_alias>    # Check current permissions for room"
        echo ""
        echo "Examples:"
        echo "  $0 list"
        echo "  $0 fix '#welcome:matrix.tantalius.com'"
        echo "  $0 fix '!AbCdEf:matrix.tantalius.com'"
        echo "  $0 fix-all"
        echo "  $0 check '#welcome:matrix.tantalius.com'"
        echo ""
        echo "Environment Variables:"
        echo "  HOMESERVER_URL  - Matrix homeserver URL (default: https://matrix.tantalius.com)"
        echo "  ADMIN_TOKEN     - Admin access token"
        echo ""
        echo "Configuration:"
        echo "  Create a .env file with your settings (see .env.example)"
        echo ""
        echo "This script allows regular users (power level 0) to participate in Element Call"
        echo "by setting the required power level for MatrixRTC events to 0."
        ;;
esac
