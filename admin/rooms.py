"""Room management functionality for Matrix administration."""

import time

from .core import MatrixClient
from .ui import FilterSortUI, ScreenManager, TerminalPaginator
from .utils import DataFormatter, ProgressMonitor, SelectionParser


class RoomManager:
    """Manage Matrix rooms through the admin API."""

    def __init__(self, client: MatrixClient, screen_manager: ScreenManager) -> None:
        self.client = client
        self.screen_manager = screen_manager

    def filter_rooms_by_criteria(
        self,
        rooms: list[dict],
        filter_text: str,
        filter_type: str = "name",
    ) -> list[dict]:
        """Filter rooms by various criteria."""
        if not filter_text:
            return rooms

        filter_text = filter_text.lower()
        filtered_rooms = []

        for room in rooms:
            if filter_type == "name":
                name = room.get("name", "").lower()
                if filter_text in name:
                    filtered_rooms.append(room)
            elif filter_type == "alias":
                alias = room.get("canonical_alias", "").lower()
                if filter_text in alias:
                    filtered_rooms.append(room)
            elif filter_type == "id":
                room_id = room.get("room_id", "").lower()
                if filter_text in room_id:
                    filtered_rooms.append(room)
            elif filter_type == "any":
                name = room.get("name", "").lower()
                alias = room.get("canonical_alias", "").lower()
                room_id = room.get("room_id", "").lower()
                if (
                    filter_text in name
                    or filter_text in alias
                    or filter_text in room_id
                ):
                    filtered_rooms.append(room)
            elif filter_type == "members":
                try:
                    # Support range filtering like "10-50" or ">20" or "<5"
                    member_count = room.get("joined_members", 0)
                    if "-" in filter_text:
                        min_val, max_val = filter_text.split("-", 1)
                        min_val = int(min_val.strip()) if min_val.strip() else 0
                        max_val = (
                            int(max_val.strip()) if max_val.strip() else float("inf")
                        )
                        if min_val <= member_count <= max_val:
                            filtered_rooms.append(room)
                    elif filter_text.startswith(">"):
                        threshold = int(filter_text[1:].strip())
                        if member_count > threshold:
                            filtered_rooms.append(room)
                    elif filter_text.startswith("<"):
                        threshold = int(filter_text[1:].strip())
                        if member_count < threshold:
                            filtered_rooms.append(room)
                    elif filter_text.startswith("="):
                        threshold = int(filter_text[1:].strip())
                        if member_count == threshold:
                            filtered_rooms.append(room)
                    else:
                        threshold = int(filter_text.strip())
                        if member_count == threshold:
                            filtered_rooms.append(room)
                except (ValueError, IndexError):
                    # Invalid member filter, skip
                    pass

        return filtered_rooms

    def sort_rooms(self, rooms: list[dict], sort_option: str) -> list[dict]:
        """Sort rooms based on the specified option."""
        if sort_option == "name_asc":
            return sorted(rooms, key=lambda r: r.get("name", "").lower())
        if sort_option == "name_desc":
            return sorted(rooms, key=lambda r: r.get("name", "").lower(), reverse=True)
        if sort_option == "alias_asc":
            return sorted(rooms, key=lambda r: r.get("canonical_alias", "").lower())
        if sort_option == "alias_desc":
            return sorted(
                rooms,
                key=lambda r: r.get("canonical_alias", "").lower(),
                reverse=True,
            )
        if sort_option == "members_asc":
            return sorted(rooms, key=lambda r: r.get("joined_members", 0))
        if sort_option == "members_desc":
            return sorted(rooms, key=lambda r: r.get("joined_members", 0), reverse=True)
        if sort_option == "id_asc":
            return sorted(rooms, key=lambda r: r.get("room_id", "").lower())
        if sort_option == "id_desc":
            return sorted(
                rooms,
                key=lambda r: r.get("room_id", "").lower(),
                reverse=True,
            )
        return rooms

    def get_room_filter_criteria(self) -> tuple[str, str]:
        """Get filter text and type from user."""
        print("\nFilter Options:")
        print("  1. Room name")
        print("  2. Room alias")
        print("  3. Room ID")
        print("  4. Any field (name, alias, or ID)")
        print("  5. Member count (examples: '5', '>10', '<20', '10-50')")
        print("  0. Cancel")

        while True:
            try:
                choice = input("Select filter type (0-5): ").strip()

                if choice == "0":
                    return "", "name"
                if choice == "1":
                    filter_text = input(
                        "Enter room name filter (partial match): ",
                    ).strip()
                    return filter_text, "name"
                if choice == "2":
                    filter_text = input("Enter alias filter (partial match): ").strip()
                    return filter_text, "alias"
                if choice == "3":
                    filter_text = input(
                        "Enter room ID filter (partial match): ",
                    ).strip()
                    return filter_text, "id"
                if choice == "4":
                    filter_text = input("Enter text to search in any field: ").strip()
                    return filter_text, "any"
                if choice == "5":
                    print("Member count examples:")
                    print("  '5' = exactly 5 members")
                    print("  '>10' = more than 10 members")
                    print("  '<20' = less than 20 members")
                    print("  '10-50' = between 10 and 50 members")
                    filter_text = input("Enter member count filter: ").strip()
                    return filter_text, "members"
                print("Invalid option. Please choose 0-5.")
            except KeyboardInterrupt:
                return "", "name"

    def get_room_sort_option(self) -> str:
        """Interactive sort option selection for rooms."""
        print("\nSort Options:")
        print("  1. Name (A-Z)")
        print("  2. Name (Z-A)")
        print("  3. Alias (A-Z)")
        print("  4. Alias (Z-A)")
        print("  5. Member count (Low to High)")
        print("  6. Member count (High to Low)")
        print("  7. Room ID (A-Z)")
        print("  8. Room ID (Z-A)")
        print("  0. No sorting")

        while True:
            try:
                choice = input("Select sort option (0-8): ").strip()
                sort_options = {
                    "0": "none",
                    "1": "name_asc",
                    "2": "name_desc",
                    "3": "alias_asc",
                    "4": "alias_desc",
                    "5": "members_asc",
                    "6": "members_desc",
                    "7": "id_asc",
                    "8": "id_desc",
                }

                if choice in sort_options:
                    return sort_options[choice]
                print("Invalid option. Please choose 0-8.")
            except KeyboardInterrupt:
                return "none"

    def list_rooms(self) -> None:
        """Enhanced list all rooms with filtering and sorting."""
        try:
            response = self.client.make_request("GET", "/_synapse/admin/v1/rooms")
            all_rooms = response.get("rooms", [])

            if not all_rooms:
                self.screen_manager.show_header("Server Rooms")
                print("No rooms found.")
                self.screen_manager.pause_for_input()
                return

            # State variables for filtering and sorting
            current_filter = ""
            current_filter_type = "name"
            current_sort = "none"
            filtered_rooms = all_rooms.copy()

            while True:
                # Apply current filter and sort
                if current_filter:
                    filtered_rooms = self.filter_rooms_by_criteria(
                        all_rooms,
                        current_filter,
                        current_filter_type,
                    )
                else:
                    filtered_rooms = all_rooms.copy()

                if current_sort != "none":
                    filtered_rooms = self.sort_rooms(filtered_rooms, current_sort)

                # Handle pagination
                paginator = TerminalPaginator(filtered_rooms, self.screen_manager)

                # Display rooms
                while True:
                    self.screen_manager.show_header("Server Rooms")

                    # Show filter/sort status
                    FilterSortUI.show_filter_sort_status(
                        current_filter,
                        current_filter_type,
                        current_sort,
                        len(all_rooms),
                        len(filtered_rooms),
                        "rooms",
                    )

                    if paginator.needs_pagination():
                        print(
                            f"Page {paginator.current_page + 1} of {paginator.total_pages}",
                        )

                    print()

                    # Show rooms
                    if filtered_rooms:
                        current_rooms = paginator.get_current_page_items()
                        start_index = (
                            paginator.current_page * paginator.items_per_page + 1
                        )

                        for i, room in enumerate(current_rooms):
                            print(
                                DataFormatter.format_room_info_enhanced(
                                    room,
                                    start_index + i,
                                ),
                            )
                    else:
                        print("No rooms match the current filter.")

                    # Show navigation options
                    FilterSortUI.show_navigation_options(
                        paginator.needs_pagination(),
                        bool(filtered_rooms),
                    )

                    choice = FilterSortUI.get_navigation_choice()

                    if choice.lower() == "q" or choice.lower() == "quit":
                        return
                    if choice.lower() == "f" or choice.lower() == "filter":
                        new_filter, new_filter_type = self.get_room_filter_criteria()
                        current_filter = new_filter
                        current_filter_type = new_filter_type
                        break  # Refresh display
                    if choice.lower() == "s" or choice.lower() == "sort":
                        current_sort = self.get_room_sort_option()
                        break  # Refresh display
                    if choice.lower() == "c" or choice.lower() == "clear":
                        current_filter = ""
                        current_filter_type = "name"
                        break  # Refresh display
                    if choice.lower() == "r" or choice.lower() == "reset":
                        current_filter = ""
                        current_filter_type = "name"
                        current_sort = "none"
                        break  # Refresh display
                    if FilterSortUI.handle_pagination_navigation(choice, paginator):
                        continue  # Page changed, refresh display
                    if choice == "" and not filtered_rooms:
                        return  # Exit if no rooms and Enter pressed
                    print("Invalid option." if choice else "")

        except Exception as e:
            self.screen_manager.show_header("Server Rooms")
            print(f"Error listing rooms: {e}")
            self.screen_manager.pause_for_input()

    def select_rooms_for_deletion(self) -> list[dict]:
        """Show room list and allow user to select rooms for deletion."""
        try:
            response = self.client.make_request("GET", "/_synapse/admin/v1/rooms")
            all_rooms = response.get("rooms", [])

            if not all_rooms:
                self.screen_manager.show_header("Delete Rooms")
                print("No rooms found.")
                self.screen_manager.pause_for_input()
                return []

            # State variables for filtering and sorting
            current_filter = ""
            current_filter_type = "name"
            current_sort = "none"
            filtered_rooms = all_rooms.copy()

            while True:
                # Apply current filter and sort
                if current_filter:
                    filtered_rooms = self.filter_rooms_by_criteria(
                        all_rooms,
                        current_filter,
                        current_filter_type,
                    )
                else:
                    filtered_rooms = all_rooms.copy()

                if current_sort != "none":
                    filtered_rooms = self.sort_rooms(filtered_rooms, current_sort)

                # Handle pagination
                paginator = TerminalPaginator(filtered_rooms, self.screen_manager)

                # Display rooms
                while True:
                    self.screen_manager.show_header("Delete Rooms - Select from List")

                    # Show filter/sort status
                    FilterSortUI.show_filter_sort_status(
                        current_filter,
                        current_filter_type,
                        current_sort,
                        len(all_rooms),
                        len(filtered_rooms),
                        "rooms",
                    )

                    if paginator.needs_pagination():
                        print(
                            f"Page {paginator.current_page + 1} of {paginator.total_pages}",
                        )

                    print()

                    # Show rooms
                    if filtered_rooms:
                        current_rooms = paginator.get_current_page_items()
                        start_index = paginator.get_current_page_start_index()

                        for i, room in enumerate(current_rooms):
                            global_index = start_index + i
                            print(
                                DataFormatter.format_room_info_enhanced(
                                    room,
                                    global_index,
                                ),
                            )
                    else:
                        print("No rooms match the current filter.")

                    # Show selection instructions
                    if filtered_rooms:
                        print("\nSelection:")
                        examples = SelectionParser.format_selection_examples(
                            len(filtered_rooms),
                        )
                        print(f"  Enter numbers to delete: {examples}")
                        print("  Or use navigation/filter options below")

                    FilterSortUI.show_navigation_options(
                        paginator.needs_pagination(),
                        bool(filtered_rooms),
                    )

                    choice = FilterSortUI.get_navigation_choice()

                    if choice.lower() == "q" or choice.lower() == "quit":
                        return []
                    if choice.lower() == "f" or choice.lower() == "filter":
                        new_filter, new_filter_type = self.get_room_filter_criteria()
                        current_filter = new_filter
                        current_filter_type = new_filter_type
                        break  # Refresh display
                    if choice.lower() == "s" or choice.lower() == "sort":
                        current_sort = self.get_room_sort_option()
                        break  # Refresh display
                    if choice.lower() == "c" or choice.lower() == "clear":
                        current_filter = ""
                        current_filter_type = "name"
                        break  # Refresh display
                    if choice.lower() == "r" or choice.lower() == "reset":
                        current_filter = ""
                        current_filter_type = "name"
                        current_sort = "none"
                        break  # Refresh display
                    if FilterSortUI.handle_pagination_navigation(choice, paginator):
                        continue  # Page changed, refresh display
                    # Try to parse as selection
                    try:
                        if not filtered_rooms:
                            print("No rooms available for selection.")
                            continue

                        selected_indices = SelectionParser.parse_selection(
                            choice,
                            len(filtered_rooms),
                        )
                        if not selected_indices:
                            print("No valid selection made.")
                            continue

                        # Get selected rooms
                        selected_rooms = []
                        for idx in selected_indices:
                            selected_rooms.append(
                                filtered_rooms[idx - 1],
                            )  # Convert to 0-based

                        return selected_rooms

                    except ValueError as e:
                        print(f"Invalid selection: {e}")
                        print("Use navigation commands or enter valid numbers/ranges.")

        except Exception as e:
            self.screen_manager.show_header("Delete Rooms")
            print(f"Error loading rooms: {e}")
            self.screen_manager.pause_for_input()
            return []

    def delete_room(self) -> None:
        """Delete rooms with interactive selection."""
        self.screen_manager.show_header("Delete Room")

        print("How would you like to select rooms to delete?")
        print("  1. Select from list (recommended)")
        print("  2. Enter room ID/alias manually")
        print("  0. Cancel")

        choice = input("\nSelect option (0-2): ").strip()

        if choice == "0":
            return
        if choice == "1":
            selected_rooms = self.select_rooms_for_deletion()
            if not selected_rooms:
                print("No rooms selected.")
                self.screen_manager.pause_for_input()
                return

            self.delete_selected_rooms(selected_rooms)

        elif choice == "2":
            room_input = input(
                "Enter room ID or alias (e.g., #room:domain.com or !id:domain.com): ",
            ).strip()
            if not room_input:
                print("No room specified.")
                self.screen_manager.pause_for_input()
                return

            try:
                room_id, display_name = self.client.resolve_room_identifier(room_input)

                # Find the room object for consistency with batch deletion
                response = self.client.make_request("GET", "/_synapse/admin/v1/rooms")
                all_rooms = response.get("rooms", [])

                selected_room = None
                for room in all_rooms:
                    if room["room_id"] == room_id:
                        selected_room = room
                        break

                if selected_room:
                    self.delete_selected_rooms([selected_room])
                else:
                    # Fall back to simple deletion if room not found in list
                    self.delete_single_room_manual(room_id, display_name)

            except Exception as e:
                print(f"Error resolving room: {e}")
                self.screen_manager.pause_for_input()
        else:
            print("Invalid option.")
            self.screen_manager.pause_for_input()

    def delete_selected_rooms(self, selected_rooms: list[dict]) -> None:
        """Delete the selected rooms after confirmation."""
        self.screen_manager.show_header("Confirm Room Deletion")

        print(f"You have selected {len(selected_rooms)} room(s) for deletion:")
        print()

        for i, room in enumerate(selected_rooms, 1):
            name = room.get("name", "Unnamed room")
            alias = room.get("canonical_alias", "No alias")
            members = room.get("joined_members", 0)
            print(f"{i}. {name}")
            print(f"   Alias: {alias}")
            print(f"   Members: {members}")
            print(f"   ID: {room['room_id']}")
            print()

        print("⚠️  WARNING: This action cannot be undone!")
        confirm = (
            input("Are you sure you want to delete these rooms? (yes/no): ")
            .strip()
            .lower()
        )

        if confirm != "yes":
            print("Deletion cancelled.")
            self.screen_manager.pause_for_input()
            return

        # Ask about purging data (applies to all rooms)
        purge = input("Purge all room data? (y/n) [default: y]: ").strip().lower()
        purge_data = purge != "n"

        # Process deletions
        successful_deletions = []
        failed_deletions = []

        for i, room in enumerate(selected_rooms, 1):
            room_id = room["room_id"]
            room_name = room.get("name", "Unnamed room")

            ProgressMonitor.show_progress(i, len(selected_rooms), room_name)

            try:
                delete_data = {
                    "block": True,
                    "purge": purge_data,
                    "message": "This room has been deleted by an administrator",
                }

                response = self.client.make_request(
                    "DELETE",
                    f"/_synapse/admin/v1/rooms/{room_id}",
                    delete_data,
                )

                if response and "delete_id" in response:
                    delete_id = response["delete_id"]
                    print(f"✓ Deletion initiated. Delete ID: {delete_id}")
                    successful_deletions.append((room, delete_id))
                else:
                    print("✗ Unexpected response format")
                    failed_deletions.append((room, "Unexpected response"))

            except Exception as e:
                print(f"✗ Error: {e}")
                failed_deletions.append((room, str(e)))

        # Show summary
        ProgressMonitor.show_operation_summary(
            "DELETION",
            len(successful_deletions),
            len(failed_deletions),
            failed_deletions,
        )

        if successful_deletions:
            print("\nMonitoring deletion progress...")
            for room, delete_id in successful_deletions:
                room_name = room.get("name", "Unnamed room")
                print(f"\nMonitoring: {room_name} (ID: {delete_id})")
                self.monitor_deletion(delete_id)

        self.screen_manager.pause_for_input()

    def delete_single_room_manual(self, room_id: str, display_name: str) -> None:
        """Delete a single room manually (fallback method)."""
        print(f"\nRoom to delete: {display_name}")
        print(f"Room ID: {room_id}")

        # Confirm deletion
        confirm = (
            input("\nAre you sure you want to delete this room? (yes/no): ")
            .strip()
            .lower()
        )
        if confirm != "yes":
            print("Deletion cancelled.")
            self.screen_manager.pause_for_input()
            return

        # Ask about purging data
        purge = input("Purge all room data? (y/n) [default: y]: ").strip().lower()
        purge_data = purge != "n"

        print(f"\nDeleting room {display_name}...")

        try:
            delete_data = {
                "block": True,
                "purge": purge_data,
                "message": "This room has been deleted by an administrator",
            }

            response = self.client.make_request(
                "DELETE",
                f"/_synapse/admin/v1/rooms/{room_id}",
                delete_data,
            )

            if response and "delete_id" in response:
                delete_id = response["delete_id"]
                print(f"Room deletion initiated. Delete ID: {delete_id}")

                # Monitor deletion progress
                self.monitor_deletion(delete_id)
            else:
                print("Unexpected response format")

        except Exception as e:
            print(f"Error deleting room: {e}")

        self.screen_manager.pause_for_input()

    def monitor_deletion(self, delete_id: str) -> None:
        """Monitor room deletion progress."""
        print(f"Monitoring deletion progress for ID: {delete_id}")

        for attempt in range(10):  # Check up to 10 times
            try:
                response = self.client.make_request(
                    "GET",
                    f"/_synapse/admin/v1/rooms/delete_status/{delete_id}",
                )

                if response:
                    status = response.get("status", "unknown")
                    print(f"  Status: {status}")

                    if status == "complete":
                        print("  ✓ Room deletion completed successfully!")
                        break
                    if status == "failed":
                        error = response.get("error", "Unknown error")
                        print(f"  ✗ Room deletion failed: {error}")
                        break

                if attempt < 9:
                    print("  Checking again in 2 seconds...")
                    time.sleep(2)

            except Exception as e:
                print(f"  Error checking deletion status: {e}")
                break

    def fix_room_permissions(self) -> None:
        """Fix room permissions for Element Call."""
        self.screen_manager.show_header("Fix Room Permissions for Element Call")

        room_input = input("Enter room ID or alias (or 'all' for all rooms): ").strip()

        if room_input.lower() == "all":
            self.fix_all_room_permissions()
        else:
            self.fix_single_room_permissions(room_input)

        self.screen_manager.pause_for_input()

    def fix_single_room_permissions(self, room_input: str) -> None:
        """Fix permissions for a single room."""
        try:
            room_id, display_name = self.client.resolve_room_identifier(room_input)

            print(f"\nFixing permissions for: {display_name}")

            # Get current power levels
            power_levels = self.client.make_request(
                "GET",
                f"/_matrix/client/v3/rooms/{room_id}/state/m.room.power_levels",
            )

            if not power_levels or "events" not in power_levels:
                print("Could not retrieve power levels")
                return

            # Update power levels for Element Call
            events = power_levels.get("events", {})
            events.update(
                {
                    "org.matrix.msc3401.call.member": 0,
                    "org.matrix.msc3401.call": 0,
                    "m.call.member": 0,
                    "m.call": 0,
                },
            )
            power_levels["events"] = events

            # Apply changes
            response = self.client.make_request(
                "PUT",
                f"/_matrix/client/v3/rooms/{room_id}/state/m.room.power_levels",
                power_levels,
            )

            if response and "event_id" in response:
                print("Permissions updated successfully!")
                print(f"  Event ID: {response['event_id']}")
            else:
                print("Failed to update permissions")

        except Exception as e:
            print(f"Error fixing permissions: {e}")

    def fix_all_room_permissions(self) -> None:
        """Fix permissions for all rooms."""
        try:
            response = self.client.make_request("GET", "/_synapse/admin/v1/rooms")
            rooms = response.get("rooms", [])

            if not rooms:
                print("No rooms found.")
                return

            print(f"Fixing permissions for {len(rooms)} rooms...")

            success_count = 0
            failed_count = 0

            for i, room in enumerate(rooms, 1):
                room_id = room["room_id"]
                room_name = room.get("name", "Unnamed room")

                ProgressMonitor.show_progress(i, len(rooms), room_name)

                try:
                    self.fix_single_room_permissions(room_id)
                    success_count += 1
                except Exception as e:
                    print(f"  Failed: {e}")
                    failed_count += 1

            print("\nSummary:")
            print(f"  Successfully updated: {success_count}")
            print(f"  Failed: {failed_count}")

        except Exception as e:
            print(f"Error fixing all room permissions: {e}")
