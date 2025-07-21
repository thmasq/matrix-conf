#!/bin/bash

# Script to delete a Matrix room using Synapse Admin API
# This completely removes the room from the server

# Variables
if [ -f .env ]; then
    echo "Loading configuration from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Function to get room ID from room alias
get_room_id_from_alias() {
    local room_alias=$1
    # URL encode the room alias
    local encoded_alias=$(echo "$room_alias" | sed 's/#/%23/g' | sed 's/:/%3A/g')
    
    curl -s -X GET "${HOMESERVER_URL}/_matrix/client/r0/directory/room/${encoded_alias}" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | \
        jq -r '.room_id'
}

# Function to delete a room
delete_room() {
    local room_id=$1
    local purge=${2:-true}  # Default to purging all data
    
    echo "Deleting room: $room_id"
    
    # Delete the room using Synapse Admin API
    response=$(curl -s -X DELETE "${HOMESERVER_URL}/_synapse/admin/v1/rooms/${room_id}" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"block\": true,
            \"purge\": ${purge},
            \"message\": \"This room has been deleted by an administrator\"
        }")
    
    echo "Response: $response"
    
    # Check if deletion was successful
    if echo "$response" | jq -e '.delete_id' > /dev/null 2>&1; then
        delete_id=$(echo "$response" | jq -r '.delete_id')
        echo "Room deletion initiated. Delete ID: $delete_id"
        echo "You can check the status with: check_deletion_status $delete_id"
    else
        echo "Error deleting room. Response: $response"
    fi
}

# Function to check deletion status
check_deletion_status() {
    local delete_id=$1
    
    curl -s -X GET "${HOMESERVER_URL}/_synapse/admin/v1/rooms/delete_status/${delete_id}" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | \
        jq '.'
}

# Function to list all rooms
list_rooms() {
    echo "Listing all rooms on the server:"
    curl -s -X GET "${HOMESERVER_URL}/_synapse/admin/v1/rooms" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | \
        jq '.rooms[] | {room_id: .room_id, name: .name, alias: .canonical_alias, members: .joined_members}'
}

# Main script logic
case "$1" in
    "list")
        list_rooms
        ;;
    "delete")
        if [ -z "$2" ]; then
            echo "Usage: $0 delete <room_id_or_alias> [purge_data]"
            echo "Example: $0 delete '!roomid:matrix.tantalius.com'"
            echo "Example: $0 delete '#roomname:matrix.tantalius.com'"
            echo "Example: $0 delete '!roomid:matrix.tantalius.com' false  # Keep history"
            exit 1
        fi
        
        room_identifier="$2"
        purge_data="${3:-true}"
        
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
        
        delete_room "$room_id" "$purge_data"
        ;;
    "status")
        if [ -z "$2" ]; then
            echo "Usage: $0 status <delete_id>"
            exit 1
        fi
        check_deletion_status "$2"
        ;;
    *)
        echo "Matrix Room Management Script"
        echo "Usage:"
        echo "  $0 list                                    # List all rooms"
        echo "  $0 delete <room_id_or_alias> [purge]      # Delete a room"
        echo "  $0 status <delete_id>                      # Check deletion status"
        echo ""
        echo "Examples:"
        echo "  $0 list"
        echo "  $0 delete '#welcome:matrix.tantalius.com'"
        echo "  $0 delete '!AbCdEf:matrix.tantalius.com'"
        echo "  $0 delete '#welcome:matrix.tantalius.com' false  # Keep message history"
        echo "  $0 status 12345"
        ;;
esac
