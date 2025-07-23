#!/usr/bin/env python3
"""
Matrix Server Administration Tool

A comprehensive administrative interface for Matrix/Synapse servers.
Consolidates room management, user administration, and server monitoring.

Usage: python3 matrix_admin.py
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import getpass
import time
import shutil
import re
from typing import Dict, List, Optional, Any, Tuple


class ScreenManager:
    """Manage terminal screen state and clearing."""
    
    def __init__(self):
        self.terminal_size = shutil.get_terminal_size()
        self.last_operation = None
    
    def clear_screen(self):
        """Clear the terminal screen."""
        print('\033[2J\033[H', end='')
    
    def refresh_size(self):
        """Refresh terminal size information."""
        self.terminal_size = shutil.get_terminal_size()
    
    def show_header(self, title: str):
        """Show a consistent header for operations."""
        self.clear_screen()
        print(title)
        print("=" * min(50, self.terminal_size.columns - 2))
    
    def pause_for_input(self, message: str = "Press Enter to continue..."):
        """Pause and wait for user input."""
        try:
            input(f"\n{message}")
        except KeyboardInterrupt:
            print()


class TerminalPaginator:
    """Handle terminal-based pagination for large lists."""
    
    def __init__(self, items: List[Any], screen_manager: ScreenManager, items_per_page: int = None):
        self.items = items
        self.screen_manager = screen_manager
        self.current_page = 0
        
        # Calculate items per page based on terminal height if not specified
        if items_per_page is None:
            # Reserve space for header, navigation, and prompt
            available_lines = max(5, self.screen_manager.terminal_size.lines - 12)
            self.items_per_page = available_lines
        else:
            self.items_per_page = items_per_page
        
        self.total_pages = max(1, (len(self.items) - 1) // self.items_per_page + 1)

    def needs_pagination(self) -> bool:
        """Check if pagination is needed."""
        return self.total_pages > 1

    def get_current_page_items(self) -> List[Any]:
        """Get items for the current page."""
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        return self.items[start_idx:end_idx]

    def get_current_page_start_index(self) -> int:
        """Get the starting index for the current page (1-based)."""
        return self.current_page * self.items_per_page + 1

    def show_navigation_help(self):
        """Show navigation instructions."""
        if not self.needs_pagination():
            return
            
        print("\nNavigation:")
        print("  [Enter] Next page  [p] Previous page  [g] Go to page  [q] Quit")
        print(f"  Page {self.current_page + 1} of {self.total_pages} ({len(self.items)} total items)")

    def navigate(self) -> bool:
        """Handle navigation input. Returns True to continue, False to quit."""
        if not self.needs_pagination():
            self.screen_manager.pause_for_input("Press Enter to return to menu...")
            return False
            
        self.show_navigation_help()
        
        while True:
            try:
                choice = input("\nAction: ").strip().lower()
                
                if choice == 'q' or choice == 'quit':
                    return False
                elif choice == '' or choice == 'n' or choice == 'next':
                    if self.current_page < self.total_pages - 1:
                        self.current_page += 1
                        return True
                    else:
                        print("Already on last page.")
                elif choice == 'p' or choice == 'prev' or choice == 'previous':
                    if self.current_page > 0:
                        self.current_page -= 1
                        return True
                    else:
                        print("Already on first page.")
                elif choice == 'g' or choice == 'goto':
                    try:
                        page_num = int(input(f"Go to page (1-{self.total_pages}): ")) - 1
                        if 0 <= page_num < self.total_pages:
                            self.current_page = page_num
                            return True
                        else:
                            print(f"Page must be between 1 and {self.total_pages}")
                    except ValueError:
                        print("Invalid page number.")
                else:
                    print("Invalid option. Use Enter, p, g, or q.")
                    
            except KeyboardInterrupt:
                return False


class SelectionParser:
    """Parse user selection input like '1', '1-5', '1,3,5', etc."""
    
    @staticmethod
    def parse_selection(selection_str: str, max_items: int) -> List[int]:
        """
        Parse selection string and return list of indices (1-based).
        
        Supports:
        - Single number: "3"
        - Range: "1-5" 
        - Comma-separated: "1,3,5"
        - Mixed: "1,3-5,7"
        """
        if not selection_str.strip():
            return []
        
        indices = set()
        parts = [part.strip() for part in selection_str.split(',')]
        
        for part in parts:
            if '-' in part:
                # Handle range
                try:
                    start, end = part.split('-', 1)
                    start_idx = int(start.strip())
                    end_idx = int(end.strip())
                    
                    if start_idx < 1 or end_idx > max_items or start_idx > end_idx:
                        raise ValueError(f"Invalid range: {part}")
                    
                    for i in range(start_idx, end_idx + 1):
                        indices.add(i)
                        
                except ValueError as e:
                    raise ValueError(f"Invalid range format '{part}': {e}")
            else:
                # Handle single number
                try:
                    idx = int(part.strip())
                    if idx < 1 or idx > max_items:
                        raise ValueError(f"Number {idx} is out of range (1-{max_items})")
                    indices.add(idx)
                except ValueError:
                    raise ValueError(f"Invalid number: {part}")
        
        return sorted(list(indices))

    @staticmethod
    def format_selection_examples(max_items: int) -> str:
        """Generate example selection strings based on available items."""
        examples = []
        
        if max_items >= 1:
            examples.append("'1' (single item)")
        if max_items >= 3:
            examples.append("'1-3' (range)")
        if max_items >= 5:
            examples.append("'1,3,5' (specific items)")
        if max_items >= 7:
            examples.append("'1,3-5,7' (mixed)")
        
        return ", ".join(examples)


class MatrixAdmin:
    def __init__(self):
        self.screen_manager = ScreenManager()
        self.config = self.load_config()
        self.base_url = self.config.get('homeserver_url', '').rstrip('/')
        self.admin_token = self.config.get('admin_token', '')
        
        if not self.base_url or not self.admin_token:
            self.setup_config()

    def load_config(self) -> Dict[str, str]:
        """Load configuration from .env file or environment variables."""
        config = {}
        
        # Try loading from .env file
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        config[key.lower()] = value
        
        # Override with environment variables
        config['homeserver_url'] = os.getenv('HOMESERVER_URL', config.get('homeserver_url', ''))
        config['admin_token'] = os.getenv('ADMIN_TOKEN', config.get('admin_token', ''))
        
        return config

    def setup_config(self):
        """Interactive configuration setup."""
        self.screen_manager.show_header("Matrix Admin Configuration Setup")
        
        if not self.base_url:
            self.base_url = input("Enter Matrix homeserver URL (e.g., https://matrix.example.com): ").strip()
            
        if not self.admin_token:
            print("\nTo get an admin token:")
            print("1. Create an admin user if you haven't already")
            print("2. Use this curl command to get a token:")
            print(f"   curl -X POST \"{self.base_url}/_matrix/client/r0/login\" \\")
            print("   -H \"Content-Type: application/json\" \\")
            print("   -d '{\"type\": \"m.login.password\", \"user\": \"admin\", \"password\": \"your_password\"}'")
            print("\n3. Copy the access_token from the response")
            
            self.admin_token = getpass.getpass("Enter admin access token: ").strip()
        
        # Test the configuration
        if self.test_connection():
            print("Configuration successful!")
            self.screen_manager.pause_for_input()
        else:
            print("Configuration failed. Please check your settings.")
            self.screen_manager.pause_for_input()
            sys.exit(1)

    def test_connection(self) -> bool:
        """Test the Matrix server connection and admin token."""
        try:
            response = self.make_request('GET', '/_matrix/client/r0/account/whoami')
            if response and 'user_id' in response:
                print(f"Connected as: {response['user_id']}")
                return True
        except Exception as e:
            print(f"Connection failed: {e}")
        return False

    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make HTTP request to Matrix server."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            'Authorization': f'Bearer {self.admin_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            if data:
                data_bytes = json.dumps(data).encode('utf-8')
                request = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
            else:
                request = urllib.request.Request(url, headers=headers, method=method)
            
            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode('utf-8'))
                
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_msg)
                raise Exception(f"HTTP {e.code}: {error_json.get('error', error_msg)}")
            except json.JSONDecodeError:
                raise Exception(f"HTTP {e.code}: {error_msg}")
        except Exception as e:
            raise Exception(f"Request failed: {e}")

    def get_room_id_from_alias(self, room_alias: str) -> Optional[str]:
        """Convert room alias to room ID."""
        try:
            encoded_alias = urllib.parse.quote(room_alias, safe='')
            response = self.make_request('GET', f'/_matrix/client/r0/directory/room/{encoded_alias}')
            return response.get('room_id') if response else None
        except:
            return None

    def resolve_room_identifier(self, identifier: str) -> Tuple[str, str]:
        """Resolve room alias or ID to room ID and display name."""
        if identifier.startswith('#'):
            room_id = self.get_room_id_from_alias(identifier)
            if not room_id:
                raise Exception(f"Could not find room with alias: {identifier}")
            return room_id, identifier
        else:
            return identifier, identifier

    def format_room_info(self, room: Dict, index: int) -> str:
        """Format room information for display."""
        alias = room.get('canonical_alias', 'No alias')
        name = room.get('name', 'Unnamed room')
        members = room.get('joined_members', 0)
        
        return f"{index:3d}. Room: {name}\n" \
               f"     ID: {room['room_id']}\n" \
               f"     Alias: {alias}\n" \
               f"     Members: {members}\n"

    def format_user_info(self, user: Dict, index: int) -> str:
        """Format user information for display."""
        user_id = user['name']
        display_name = user.get('displayname', 'No display name')
        is_admin = user.get('admin', False)
        is_deactivated = user.get('deactivated', False)
        
        status = "ADMIN" if is_admin else "USER"
        if is_deactivated:
            status += " (DEACTIVATED)"
        
        return f"{index:3d}. {user_id}\n" \
               f"     Display: {display_name}\n" \
               f"     Status: {status}\n"

    # Room filtering and sorting methods
    def filter_rooms_by_criteria(self, rooms: List[Dict], filter_text: str, filter_type: str = "name") -> List[Dict]:
        """Filter rooms by various criteria."""
        if not filter_text:
            return rooms
        
        filter_text = filter_text.lower()
        filtered_rooms = []
        
        for room in rooms:
            if filter_type == "name":
                name = room.get('name', '').lower()
                if filter_text in name:
                    filtered_rooms.append(room)
            elif filter_type == "alias":
                alias = room.get('canonical_alias', '').lower()
                if filter_text in alias:
                    filtered_rooms.append(room)
            elif filter_type == "id":
                room_id = room.get('room_id', '').lower()
                if filter_text in room_id:
                    filtered_rooms.append(room)
            elif filter_type == "any":
                name = room.get('name', '').lower()
                alias = room.get('canonical_alias', '').lower()
                room_id = room.get('room_id', '').lower()
                if filter_text in name or filter_text in alias or filter_text in room_id:
                    filtered_rooms.append(room)
            elif filter_type == "members":
                try:
                    # Support range filtering like "10-50" or ">20" or "<5"
                    member_count = room.get('joined_members', 0)
                    if '-' in filter_text:
                        min_val, max_val = filter_text.split('-', 1)
                        min_val = int(min_val.strip()) if min_val.strip() else 0
                        max_val = int(max_val.strip()) if max_val.strip() else float('inf')
                        if min_val <= member_count <= max_val:
                            filtered_rooms.append(room)
                    elif filter_text.startswith('>'):
                        threshold = int(filter_text[1:].strip())
                        if member_count > threshold:
                            filtered_rooms.append(room)
                    elif filter_text.startswith('<'):
                        threshold = int(filter_text[1:].strip())
                        if member_count < threshold:
                            filtered_rooms.append(room)
                    elif filter_text.startswith('='):
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

    def sort_rooms(self, rooms: List[Dict], sort_option: str) -> List[Dict]:
        """Sort rooms based on the specified option."""
        if sort_option == "name_asc":
            return sorted(rooms, key=lambda r: r.get('name', '').lower())
        elif sort_option == "name_desc":
            return sorted(rooms, key=lambda r: r.get('name', '').lower(), reverse=True)
        elif sort_option == "alias_asc":
            return sorted(rooms, key=lambda r: r.get('canonical_alias', '').lower())
        elif sort_option == "alias_desc":
            return sorted(rooms, key=lambda r: r.get('canonical_alias', '').lower(), reverse=True)
        elif sort_option == "members_asc":
            return sorted(rooms, key=lambda r: r.get('joined_members', 0))
        elif sort_option == "members_desc":
            return sorted(rooms, key=lambda r: r.get('joined_members', 0), reverse=True)
        elif sort_option == "id_asc":
            return sorted(rooms, key=lambda r: r.get('room_id', '').lower())
        elif sort_option == "id_desc":
            return sorted(rooms, key=lambda r: r.get('room_id', '').lower(), reverse=True)
        else:
            return rooms

    def show_room_filter_options(self, current_filter: str, current_filter_type: str, current_sort: str, total_rooms: int, filtered_count: int):
        """Display current filter and sort status for rooms."""
        print(f"Rooms: {filtered_count}/{total_rooms}")
        
        if current_filter:
            filter_type_names = {
                "name": "Name",
                "alias": "Alias", 
                "id": "ID",
                "any": "Any field",
                "members": "Member count"
            }
            filter_type_display = filter_type_names.get(current_filter_type, current_filter_type)
            print(f"Filter: '{current_filter}' ({filter_type_display})")
        
        if current_sort != "none":
            sort_names = {
                "name_asc": "Name (A-Z)",
                "name_desc": "Name (Z-A)",
                "alias_asc": "Alias (A-Z)", 
                "alias_desc": "Alias (Z-A)",
                "members_asc": "Members (Low to High)",
                "members_desc": "Members (High to Low)",
                "id_asc": "Room ID (A-Z)",
                "id_desc": "Room ID (Z-A)"
            }
            print(f"Sort: {sort_names.get(current_sort, current_sort)}")

    def get_room_filter_criteria(self) -> Tuple[str, str]:
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
                elif choice == "1":
                    filter_text = input("Enter room name filter (partial match): ").strip()
                    return filter_text, "name"
                elif choice == "2":
                    filter_text = input("Enter alias filter (partial match): ").strip()
                    return filter_text, "alias"
                elif choice == "3":
                    filter_text = input("Enter room ID filter (partial match): ").strip()
                    return filter_text, "id"
                elif choice == "4":
                    filter_text = input("Enter text to search in any field: ").strip()
                    return filter_text, "any"
                elif choice == "5":
                    print("Member count examples:")
                    print("  '5' = exactly 5 members")
                    print("  '>10' = more than 10 members") 
                    print("  '<20' = less than 20 members")
                    print("  '10-50' = between 10 and 50 members")
                    filter_text = input("Enter member count filter: ").strip()
                    return filter_text, "members"
                else:
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
                    "8": "id_desc"
                }
                
                if choice in sort_options:
                    return sort_options[choice]
                else:
                    print("Invalid option. Please choose 0-8.")
            except KeyboardInterrupt:
                return "none"

    def format_room_info_enhanced(self, room: Dict, index: int) -> str:
        """Enhanced format room information for display with member count highlight."""
        alias = room.get('canonical_alias', 'No alias')
        name = room.get('name', 'Unnamed room')
        members = room.get('joined_members', 0)
        
        # Add member count indicator
        if members == 0:
            member_indicator = "👤 Empty"
        elif members == 1:
            member_indicator = "👤 1 member"
        elif members < 10:
            member_indicator = f"👥 {members} members"
        else:
            member_indicator = f"👥 {members} members"
        
        return f"{index:3d}. {member_indicator} {name}\n" \
               f"     ID: {room['room_id']}\n" \
               f"     Alias: {alias}\n"

    def select_rooms_for_deletion(self) -> List[Dict]:
        """Show room list and allow user to select rooms for deletion."""
        try:
            response = self.make_request('GET', '/_synapse/admin/v1/rooms')
            all_rooms = response.get('rooms', [])
            
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
                    filtered_rooms = self.filter_rooms_by_criteria(all_rooms, current_filter, current_filter_type)
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
                    self.show_room_filter_options(current_filter, current_filter_type, current_sort, 
                                                len(all_rooms), len(filtered_rooms))
                    
                    if paginator.needs_pagination():
                        print(f"Page {paginator.current_page + 1} of {paginator.total_pages}")
                    
                    print()
                    
                    # Show rooms
                    if filtered_rooms:
                        current_rooms = paginator.get_current_page_items()
                        start_index = paginator.get_current_page_start_index()
                        
                        for i, room in enumerate(current_rooms):
                            global_index = start_index + i
                            print(self.format_room_info_enhanced(room, global_index))
                    else:
                        print("No rooms match the current filter.")
                    
                    # Show selection instructions
                    if filtered_rooms:
                        print("\nSelection:")
                        examples = SelectionParser.format_selection_examples(len(filtered_rooms))
                        print(f"  Enter numbers to delete: {examples}")
                        print("  Or use navigation/filter options below")
                    
                    # Handle navigation and commands
                    if paginator.needs_pagination() and filtered_rooms:
                        print("\nNavigation:")
                        print("  [Enter] Next page  [p] Previous page  [g] Go to page")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Cancel")
                    else:
                        print("\nOptions:")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Cancel")
                    
                    try:
                        choice = input("\nAction: ").strip()
                        
                        if choice.lower() == 'q' or choice.lower() == 'quit':
                            return []
                        elif choice.lower() == 'f' or choice.lower() == 'filter':
                            new_filter, new_filter_type = self.get_room_filter_criteria()
                            current_filter = new_filter
                            current_filter_type = new_filter_type
                            break  # Refresh display
                        elif choice.lower() == 's' or choice.lower() == 'sort':
                            current_sort = self.get_room_sort_option()
                            break  # Refresh display
                        elif choice.lower() == 'c' or choice.lower() == 'clear':
                            current_filter = ""
                            current_filter_type = "name"
                            break  # Refresh display
                        elif choice.lower() == 'r' or choice.lower() == 'reset':
                            current_filter = ""
                            current_filter_type = "name"
                            current_sort = "none"
                            break  # Refresh display
                        elif choice == '' or choice.lower() == 'n' or choice.lower() == 'next':
                            if paginator.needs_pagination() and filtered_rooms:
                                if paginator.current_page < paginator.total_pages - 1:
                                    paginator.current_page += 1
                                else:
                                    print("Already on last page.")
                            else:
                                continue
                        elif choice.lower() == 'p' or choice.lower() == 'prev' or choice.lower() == 'previous':
                            if paginator.needs_pagination() and paginator.current_page > 0:
                                paginator.current_page -= 1
                            else:
                                print("Already on first page." if paginator.needs_pagination() else "Invalid option.")
                        elif choice.lower() == 'g' or choice.lower() == 'goto':
                            if paginator.needs_pagination():
                                try:
                                    page_num = int(input(f"Go to page (1-{paginator.total_pages}): ")) - 1
                                    if 0 <= page_num < paginator.total_pages:
                                        paginator.current_page = page_num
                                    else:
                                        print(f"Page must be between 1 and {paginator.total_pages}")
                                except ValueError:
                                    print("Invalid page number.")
                            else:
                                print("No pagination available.")
                        else:
                            # Try to parse as selection
                            try:
                                if not filtered_rooms:
                                    print("No rooms available for selection.")
                                    continue
                                    
                                selected_indices = SelectionParser.parse_selection(choice, len(filtered_rooms))
                                if not selected_indices:
                                    print("No valid selection made.")
                                    continue
                                
                                # Get selected rooms
                                selected_rooms = []
                                for idx in selected_indices:
                                    selected_rooms.append(filtered_rooms[idx - 1])  # Convert to 0-based
                                
                                return selected_rooms
                                
                            except ValueError as e:
                                print(f"Invalid selection: {e}")
                                print("Use navigation commands or enter valid numbers/ranges.")
                        
                    except KeyboardInterrupt:
                        return []
                
        except Exception as e:
            self.screen_manager.show_header("Delete Rooms")
            print(f"Error loading rooms: {e}")
            self.screen_manager.pause_for_input()
            return []

    # Room Management Methods
    def list_rooms(self):
        """Enhanced list all rooms with filtering and sorting."""
        try:
            response = self.make_request('GET', '/_synapse/admin/v1/rooms')
            all_rooms = response.get('rooms', [])
            
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
                    filtered_rooms = self.filter_rooms_by_criteria(all_rooms, current_filter, current_filter_type)
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
                    self.show_room_filter_options(current_filter, current_filter_type, current_sort, 
                                                len(all_rooms), len(filtered_rooms))
                    
                    if paginator.needs_pagination():
                        print(f"Page {paginator.current_page + 1} of {paginator.total_pages}")
                    
                    print()
                    
                    # Show rooms
                    if filtered_rooms:
                        current_rooms = paginator.get_current_page_items()
                        start_index = paginator.current_page * paginator.items_per_page + 1
                        
                        for i, room in enumerate(current_rooms):
                            print(self.format_room_info_enhanced(room, start_index + i))
                    else:
                        print("No rooms match the current filter.")
                    
                    # Handle navigation and commands
                    if paginator.needs_pagination() and filtered_rooms:
                        print("\nNavigation:")
                        print("  [Enter] Next page  [p] Previous page  [g] Go to page")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Quit")
                    else:
                        print("\nOptions:")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Quit")
                        if not filtered_rooms:
                            print("  [Enter] Continue")
                    
                    try:
                        choice = input("\nAction: ").strip().lower()
                        
                        if choice == 'q' or choice == 'quit':
                            return
                        elif choice == 'f' or choice == 'filter':
                            new_filter, new_filter_type = self.get_room_filter_criteria()
                            current_filter = new_filter
                            current_filter_type = new_filter_type
                            paginator = TerminalPaginator(
                                self.filter_rooms_by_criteria(all_rooms, current_filter, current_filter_type) if current_filter 
                                else all_rooms, self.screen_manager)
                            break  # Refresh display
                        elif choice == 's' or choice == 'sort':
                            current_sort = self.get_room_sort_option()
                            break  # Refresh display
                        elif choice == 'c' or choice == 'clear':
                            current_filter = ""
                            current_filter_type = "name"
                            break  # Refresh display
                        elif choice == 'r' or choice == 'reset':
                            current_filter = ""
                            current_filter_type = "name"
                            current_sort = "none"
                            break  # Refresh display
                        elif choice == '' or choice == 'n' or choice == 'next':
                            if paginator.needs_pagination() and filtered_rooms:
                                if paginator.current_page < paginator.total_pages - 1:
                                    paginator.current_page += 1
                                else:
                                    print("Already on last page.")
                            elif not filtered_rooms:
                                continue  # Just refresh display
                            else:
                                return  # Exit if no pagination needed
                        elif choice == 'p' or choice == 'prev' or choice == 'previous':
                            if paginator.needs_pagination() and paginator.current_page > 0:
                                paginator.current_page -= 1
                            else:
                                print("Already on first page." if paginator.needs_pagination() else "Invalid option.")
                        elif choice == 'g' or choice == 'goto':
                            if paginator.needs_pagination():
                                try:
                                    page_num = int(input(f"Go to page (1-{paginator.total_pages}): ")) - 1
                                    if 0 <= page_num < paginator.total_pages:
                                        paginator.current_page = page_num
                                    else:
                                        print(f"Page must be between 1 and {paginator.total_pages}")
                                except ValueError:
                                    print("Invalid page number.")
                            else:
                                print("No pagination available.")
                        else:
                            print("Invalid option.")
                            
                    except KeyboardInterrupt:
                        return
                
        except Exception as e:
            self.screen_manager.show_header("Server Rooms")
            print(f"Error listing rooms: {e}")
            self.screen_manager.pause_for_input()

    def delete_room(self):
        """Delete rooms with interactive selection."""
        self.screen_manager.show_header("Delete Room")
        
        print("How would you like to select rooms to delete?")
        print("  1. Select from list (recommended)")
        print("  2. Enter room ID/alias manually")
        print("  0. Cancel")
        
        choice = input("\nSelect option (0-2): ").strip()
        
        if choice == "0":
            return
        elif choice == "1":
            selected_rooms = self.select_rooms_for_deletion()
            if not selected_rooms:
                print("No rooms selected.")
                self.screen_manager.pause_for_input()
                return
            
            self.delete_selected_rooms(selected_rooms)
            
        elif choice == "2":
            room_input = input("Enter room ID or alias (e.g., #room:domain.com or !id:domain.com): ").strip()
            if not room_input:
                print("No room specified.")
                self.screen_manager.pause_for_input()
                return
            
            try:
                room_id, display_name = self.resolve_room_identifier(room_input)
                
                # Find the room object for consistency with batch deletion
                response = self.make_request('GET', '/_synapse/admin/v1/rooms')
                all_rooms = response.get('rooms', [])
                
                selected_room = None
                for room in all_rooms:
                    if room['room_id'] == room_id:
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

    def delete_selected_rooms(self, selected_rooms: List[Dict]):
        """Delete the selected rooms after confirmation."""
        self.screen_manager.show_header("Confirm Room Deletion")
        
        print(f"You have selected {len(selected_rooms)} room(s) for deletion:")
        print()
        
        for i, room in enumerate(selected_rooms, 1):
            name = room.get('name', 'Unnamed room')
            alias = room.get('canonical_alias', 'No alias')
            members = room.get('joined_members', 0)
            print(f"{i}. {name}")
            print(f"   Alias: {alias}")
            print(f"   Members: {members}")
            print(f"   ID: {room['room_id']}")
            print()
        
        print("⚠️  WARNING: This action cannot be undone!")
        confirm = input("Are you sure you want to delete these rooms? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Deletion cancelled.")
            self.screen_manager.pause_for_input()
            return
        
        # Ask about purging data (applies to all rooms)
        purge = input("Purge all room data? (y/n) [default: y]: ").strip().lower()
        purge_data = purge != 'n'
        
        # Process deletions
        successful_deletions = []
        failed_deletions = []
        
        for i, room in enumerate(selected_rooms, 1):
            room_id = room['room_id']
            room_name = room.get('name', 'Unnamed room')
            
            print(f"\n[{i}/{len(selected_rooms)}] Deleting: {room_name}")
            
            try:
                delete_data = {
                    "block": True,
                    "purge": purge_data,
                    "message": "This room has been deleted by an administrator"
                }
                
                response = self.make_request('DELETE', f'/_synapse/admin/v1/rooms/{room_id}', delete_data)
                
                if response and 'delete_id' in response:
                    delete_id = response['delete_id']
                    print(f"✓ Deletion initiated. Delete ID: {delete_id}")
                    successful_deletions.append((room, delete_id))
                else:
                    print("✗ Unexpected response format")
                    failed_deletions.append((room, "Unexpected response"))
                    
            except Exception as e:
                print(f"✗ Error: {e}")
                failed_deletions.append((room, str(e)))
        
        # Show summary
        print(f"\n" + "="*50)
        print("DELETION SUMMARY")
        print("="*50)
        print(f"Successfully initiated: {len(successful_deletions)}")
        print(f"Failed: {len(failed_deletions)}")
        
        if failed_deletions:
            print("\nFailed deletions:")
            for room, error in failed_deletions:
                room_name = room.get('name', 'Unnamed room')
                print(f"  - {room_name}: {error}")
        
        if successful_deletions:
            print(f"\nMonitoring deletion progress...")
            for room, delete_id in successful_deletions:
                room_name = room.get('name', 'Unnamed room')
                print(f"\nMonitoring: {room_name} (ID: {delete_id})")
                self.monitor_deletion(delete_id)
        
        self.screen_manager.pause_for_input()

    def delete_single_room_manual(self, room_id: str, display_name: str):
        """Delete a single room manually (fallback method)."""
        print(f"\nRoom to delete: {display_name}")
        print(f"Room ID: {room_id}")
        
        # Confirm deletion
        confirm = input("\nAre you sure you want to delete this room? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Deletion cancelled.")
            self.screen_manager.pause_for_input()
            return
        
        # Ask about purging data
        purge = input("Purge all room data? (y/n) [default: y]: ").strip().lower()
        purge_data = purge != 'n'
        
        print(f"\nDeleting room {display_name}...")
        
        try:
            delete_data = {
                "block": True,
                "purge": purge_data,
                "message": "This room has been deleted by an administrator"
            }
            
            response = self.make_request('DELETE', f'/_synapse/admin/v1/rooms/{room_id}', delete_data)
            
            if response and 'delete_id' in response:
                delete_id = response['delete_id']
                print(f"Room deletion initiated. Delete ID: {delete_id}")
                
                # Monitor deletion progress
                self.monitor_deletion(delete_id)
            else:
                print("Unexpected response format")
                
        except Exception as e:
            print(f"Error deleting room: {e}")
            
        self.screen_manager.pause_for_input()

    def monitor_deletion(self, delete_id: str):
        """Monitor room deletion progress."""
        print(f"Monitoring deletion progress for ID: {delete_id}")
        
        for attempt in range(10):  # Check up to 10 times
            try:
                response = self.make_request('GET', f'/_synapse/admin/v1/rooms/delete_status/{delete_id}')
                
                if response:
                    status = response.get('status', 'unknown')
                    print(f"  Status: {status}")
                    
                    if status == 'complete':
                        print("  ✓ Room deletion completed successfully!")
                        break
                    elif status == 'failed':
                        error = response.get('error', 'Unknown error')
                        print(f"  ✗ Room deletion failed: {error}")
                        break
                
                if attempt < 9:
                    print("  Checking again in 2 seconds...")
                    time.sleep(2)
                    
            except Exception as e:
                print(f"  Error checking deletion status: {e}")
                break

    def fix_room_permissions(self):
        """Fix room permissions for Element Call."""
        self.screen_manager.show_header("Fix Room Permissions for Element Call")
        
        room_input = input("Enter room ID or alias (or 'all' for all rooms): ").strip()
        
        if room_input.lower() == 'all':
            self.fix_all_room_permissions()
        else:
            self.fix_single_room_permissions(room_input)
        
        self.screen_manager.pause_for_input()

    def fix_single_room_permissions(self, room_input: str):
        """Fix permissions for a single room."""
        try:
            room_id, display_name = self.resolve_room_identifier(room_input)
            
            print(f"\nFixing permissions for: {display_name}")
            
            # Get current power levels
            power_levels = self.make_request('GET', f'/_matrix/client/v3/rooms/{room_id}/state/m.room.power_levels')
            
            if not power_levels or 'events' not in power_levels:
                print("Could not retrieve power levels")
                return
            
            # Update power levels for Element Call
            events = power_levels.get('events', {})
            events.update({
                'org.matrix.msc3401.call.member': 0,
                'org.matrix.msc3401.call': 0,
                'm.call.member': 0,
                'm.call': 0
            })
            power_levels['events'] = events
            
            # Apply changes
            response = self.make_request('PUT', f'/_matrix/client/v3/rooms/{room_id}/state/m.room.power_levels', power_levels)
            
            if response and 'event_id' in response:
                print(f"Permissions updated successfully!")
                print(f"  Event ID: {response['event_id']}")
            else:
                print("Failed to update permissions")
                
        except Exception as e:
            print(f"Error fixing permissions: {e}")

    def fix_all_room_permissions(self):
        """Fix permissions for all rooms."""
        try:
            response = self.make_request('GET', '/_synapse/admin/v1/rooms')
            rooms = response.get('rooms', [])
            
            if not rooms:
                print("No rooms found.")
                return
            
            print(f"Fixing permissions for {len(rooms)} rooms...")
            
            success_count = 0
            failed_count = 0
            
            for i, room in enumerate(rooms, 1):
                room_id = room['room_id']
                room_name = room.get('name', 'Unnamed room')
                
                print(f"[{i}/{len(rooms)}] Processing: {room_name}")
                
                try:
                    self.fix_single_room_permissions(room_id)
                    success_count += 1
                except Exception as e:
                    print(f"  Failed: {e}")
                    failed_count += 1
            
            print(f"\nSummary:")
            print(f"  Successfully updated: {success_count}")
            print(f"  Failed: {failed_count}")
            
        except Exception as e:
            print(f"Error fixing all room permissions: {e}")

    # User Management Methods
    def filter_users_by_name(self, users: List[Dict], filter_text: str) -> List[Dict]:
        """Filter users by name (user ID or display name)."""
        if not filter_text:
            return users
        
        filter_text = filter_text.lower()
        filtered_users = []
        
        for user in users:
            user_id = user.get('name', '').lower()
            display_name = user.get('displayname', '').lower()
            
            if filter_text in user_id or filter_text in display_name:
                filtered_users.append(user)
        
        return filtered_users

    def sort_users(self, users: List[Dict], sort_option: str) -> List[Dict]:
        """Sort users based on the specified option."""
        if sort_option == "name_asc":
            return sorted(users, key=lambda u: u.get('name', '').lower())
        elif sort_option == "name_desc":
            return sorted(users, key=lambda u: u.get('name', '').lower(), reverse=True)
        elif sort_option == "display_asc":
            return sorted(users, key=lambda u: u.get('displayname', '').lower())
        elif sort_option == "display_desc":
            return sorted(users, key=lambda u: u.get('displayname', '').lower(), reverse=True)
        elif sort_option == "role":
            # Sort by role: admins first, then regular users, then deactivated
            def role_sort_key(user):
                is_admin = user.get('admin', False)
                is_deactivated = user.get('deactivated', False)
                
                if is_deactivated:
                    return (2, user.get('name', '').lower())  # Deactivated last
                elif is_admin:
                    return (0, user.get('name', '').lower())  # Admins first
                else:
                    return (1, user.get('name', '').lower())  # Regular users middle
            
            return sorted(users, key=role_sort_key)
        else:
            return users

    def get_user_role_tag(self, user: Dict) -> str:
        """Get a colored role tag for the user."""
        is_admin = user.get('admin', False)
        is_deactivated = user.get('deactivated', False)
        
        if is_deactivated:
            return "🚫 DEACTIVATED"
        elif is_admin:
            return "👑 ADMIN"
        else:
            return "👤 USER"

    def format_user_info_enhanced(self, user: Dict, index: int) -> str:
        """Enhanced format user information for display with role tags."""
        user_id = user['name']
        display_name = user.get('displayname', 'No display name')
        role_tag = self.get_user_role_tag(user)
        
        return f"{index:3d}. {role_tag} {user_id}\n" \
               f"     Display: {display_name}\n"

    def show_user_filter_options(self, current_filter: str, current_sort: str, total_users: int, filtered_count: int):
        """Display current filter and sort status."""
        print(f"Users: {filtered_count}/{total_users}")
        
        if current_filter:
            print(f"Filter: '{current_filter}'")
        if current_sort != "none":
            sort_names = {
                "name_asc": "Name (A-Z)",
                "name_desc": "Name (Z-A)", 
                "display_asc": "Display Name (A-Z)",
                "display_desc": "Display Name (Z-A)",
                "role": "Role (Admin → User → Deactivated)"
            }
            print(f"Sort: {sort_names.get(current_sort, current_sort)}")

    def get_sort_option(self) -> str:
        """Interactive sort option selection."""
        print("\nSort Options:")
        print("  1. Name (A-Z)")
        print("  2. Name (Z-A)")
        print("  3. Display Name (A-Z)")
        print("  4. Display Name (Z-A)")
        print("  5. Role (Admin → User → Deactivated)")
        print("  0. No sorting")
        
        while True:
            try:
                choice = input("Select sort option (0-5): ").strip()
                sort_options = {
                    "0": "none",
                    "1": "name_asc",
                    "2": "name_desc", 
                    "3": "display_asc",
                    "4": "display_desc",
                    "5": "role"
                }
                
                if choice in sort_options:
                    return sort_options[choice]
                else:
                    print("Invalid option. Please choose 0-5.")
            except KeyboardInterrupt:
                return "none"

    def select_users_for_deactivation(self) -> List[Dict]:
        """Show user list and allow user to select users for deactivation."""
        try:
            response = self.make_request('GET', '/_synapse/admin/v2/users')
            all_users = response.get('users', [])
            
            # Filter out already deactivated users
            active_users = [user for user in all_users if not user.get('deactivated', False)]
            
            if not active_users:
                self.screen_manager.show_header("Deactivate Users")
                print("No active users found.")
                self.screen_manager.pause_for_input()
                return []
            
            # State variables for filtering and sorting
            current_filter = ""
            current_sort = "none"
            filtered_users = active_users.copy()
            
            while True:
                # Apply current filter and sort
                if current_filter:
                    filtered_users = self.filter_users_by_name(active_users, current_filter)
                else:
                    filtered_users = active_users.copy()
                
                if current_sort != "none":
                    filtered_users = self.sort_users(filtered_users, current_sort)
                
                # Handle pagination
                paginator = TerminalPaginator(filtered_users, self.screen_manager)
                
                # Display users
                while True:
                    self.screen_manager.show_header("Deactivate Users - Select from List")
                    
                    # Show filter/sort status
                    self.show_user_filter_options(current_filter, current_sort, 
                                                len(active_users), len(filtered_users))
                    
                    if paginator.needs_pagination():
                        print(f"Page {paginator.current_page + 1} of {paginator.total_pages}")
                    
                    print()
                    
                    # Show users
                    if filtered_users:
                        current_users = paginator.get_current_page_items()
                        start_index = paginator.get_current_page_start_index()
                        
                        for i, user in enumerate(current_users):
                            global_index = start_index + i
                            print(self.format_user_info_enhanced(user, global_index))
                    else:
                        print("No users match the current filter.")
                    
                    # Show selection instructions
                    if filtered_users:
                        print("\nSelection:")
                        examples = SelectionParser.format_selection_examples(len(filtered_users))
                        print(f"  Enter numbers to deactivate: {examples}")
                        print("  Or use navigation/filter options below")
                    
                    # Handle navigation and commands
                    if paginator.needs_pagination() and filtered_users:
                        print("\nNavigation:")
                        print("  [Enter] Next page  [p] Previous page  [g] Go to page")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Cancel")
                    else:
                        print("\nOptions:")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Cancel")
                    
                    try:
                        choice = input("\nAction: ").strip()
                        
                        if choice.lower() == 'q' or choice.lower() == 'quit':
                            return []
                        elif choice.lower() == 'f' or choice.lower() == 'filter':
                            new_filter = input("Enter name filter (partial match): ").strip()
                            current_filter = new_filter
                            break  # Refresh display
                        elif choice.lower() == 's' or choice.lower() == 'sort':
                            current_sort = self.get_sort_option()
                            break  # Refresh display
                        elif choice.lower() == 'c' or choice.lower() == 'clear':
                            current_filter = ""
                            break  # Refresh display
                        elif choice.lower() == 'r' or choice.lower() == 'reset':
                            current_filter = ""
                            current_sort = "none"
                            break  # Refresh display
                        elif choice == '' or choice.lower() == 'n' or choice.lower() == 'next':
                            if paginator.needs_pagination() and filtered_users:
                                if paginator.current_page < paginator.total_pages - 1:
                                    paginator.current_page += 1
                                else:
                                    print("Already on last page.")
                            else:
                                continue
                        elif choice.lower() == 'p' or choice.lower() == 'prev' or choice.lower() == 'previous':
                            if paginator.needs_pagination() and paginator.current_page > 0:
                                paginator.current_page -= 1
                            else:
                                print("Already on first page." if paginator.needs_pagination() else "Invalid option.")
                        elif choice.lower() == 'g' or choice.lower() == 'goto':
                            if paginator.needs_pagination():
                                try:
                                    page_num = int(input(f"Go to page (1-{paginator.total_pages}): ")) - 1
                                    if 0 <= page_num < paginator.total_pages:
                                        paginator.current_page = page_num
                                    else:
                                        print(f"Page must be between 1 and {paginator.total_pages}")
                                except ValueError:
                                    print("Invalid page number.")
                            else:
                                print("No pagination available.")
                        else:
                            # Try to parse as selection
                            try:
                                if not filtered_users:
                                    print("No users available for selection.")
                                    continue
                                    
                                selected_indices = SelectionParser.parse_selection(choice, len(filtered_users))
                                if not selected_indices:
                                    print("No valid selection made.")
                                    continue
                                
                                # Get selected users
                                selected_users = []
                                for idx in selected_indices:
                                    selected_users.append(filtered_users[idx - 1])  # Convert to 0-based
                                
                                return selected_users
                                
                            except ValueError as e:
                                print(f"Invalid selection: {e}")
                                print("Use navigation commands or enter valid numbers/ranges.")
                        
                    except KeyboardInterrupt:
                        return []
                
        except Exception as e:
            self.screen_manager.show_header("Deactivate Users")
            print(f"Error loading users: {e}")
            self.screen_manager.pause_for_input()
            return []

    def list_users(self):
        """Enhanced list all users with filtering and sorting."""
        try:
            response = self.make_request('GET', '/_synapse/admin/v2/users')
            all_users = response.get('users', [])
            
            if not all_users:
                self.screen_manager.show_header("Server Users")
                print("No users found.")
                self.screen_manager.pause_for_input()
                return
            
            # State variables for filtering and sorting
            current_filter = ""
            current_sort = "none"
            filtered_users = all_users.copy()
            
            while True:
                # Apply current filter and sort
                if current_filter:
                    filtered_users = self.filter_users_by_name(all_users, current_filter)
                else:
                    filtered_users = all_users.copy()
                
                if current_sort != "none":
                    filtered_users = self.sort_users(filtered_users, current_sort)
                
                # Handle pagination
                paginator = TerminalPaginator(filtered_users, self.screen_manager)
                
                # Display users
                while True:
                    self.screen_manager.show_header("Server Users")
                    
                    # Show filter/sort status
                    self.show_user_filter_options(current_filter, current_sort, 
                                                len(all_users), len(filtered_users))
                    
                    if paginator.needs_pagination():
                        print(f"Page {paginator.current_page + 1} of {paginator.total_pages}")
                    
                    print()
                    
                    # Show users
                    if filtered_users:
                        current_users = paginator.get_current_page_items()
                        start_index = paginator.current_page * paginator.items_per_page + 1
                        
                        for i, user in enumerate(current_users):
                            print(self.format_user_info_enhanced(user, start_index + i))
                    else:
                        print("No users match the current filter.")
                    
                    # Handle navigation and commands
                    if paginator.needs_pagination() and filtered_users:
                        print("\nNavigation:")
                        print("  [Enter] Next page  [p] Previous page  [g] Go to page")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Quit")
                    else:
                        print("\nOptions:")
                        print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Quit")
                        if not filtered_users:
                            print("  [Enter] Continue")
                    
                    try:
                        choice = input("\nAction: ").strip().lower()
                        
                        if choice == 'q' or choice == 'quit':
                            return
                        elif choice == 'f' or choice == 'filter':
                            new_filter = input("Enter name filter (partial match): ").strip()
                            current_filter = new_filter
                            paginator = TerminalPaginator(
                                self.filter_users_by_name(all_users, current_filter) if current_filter 
                                else all_users, self.screen_manager)
                            break  # Refresh display
                        elif choice == 's' or choice == 'sort':
                            current_sort = self.get_sort_option()
                            break  # Refresh display
                        elif choice == 'c' or choice == 'clear':
                            current_filter = ""
                            break  # Refresh display
                        elif choice == 'r' or choice == 'reset':
                            current_filter = ""
                            current_sort = "none"
                            break  # Refresh display
                        elif choice == '' or choice == 'n' or choice == 'next':
                            if paginator.needs_pagination() and filtered_users:
                                if paginator.current_page < paginator.total_pages - 1:
                                    paginator.current_page += 1
                                else:
                                    print("Already on last page.")
                            elif not filtered_users:
                                continue  # Just refresh display
                            else:
                                return  # Exit if no pagination needed
                        elif choice == 'p' or choice == 'prev' or choice == 'previous':
                            if paginator.needs_pagination() and paginator.current_page > 0:
                                paginator.current_page -= 1
                            else:
                                print("Already on first page." if paginator.needs_pagination() else "Invalid option.")
                        elif choice == 'g' or choice == 'goto':
                            if paginator.needs_pagination():
                                try:
                                    page_num = int(input(f"Go to page (1-{paginator.total_pages}): ")) - 1
                                    if 0 <= page_num < paginator.total_pages:
                                        paginator.current_page = page_num
                                    else:
                                        print(f"Page must be between 1 and {paginator.total_pages}")
                                except ValueError:
                                    print("Invalid page number.")
                            else:
                                print("No pagination available.")
                        else:
                            print("Invalid option.")
                            
                    except KeyboardInterrupt:
                        return
                
        except Exception as e:
            self.screen_manager.show_header("Server Users")
            print(f"Error listing users: {e}")
            self.screen_manager.pause_for_input()

    def create_user(self):
        """Create a new user interactively."""
        self.screen_manager.show_header("Create New User")
        
        username = input("Username (without @domain): ").strip()
        if not username:
            print("Username required.")
            self.screen_manager.pause_for_input()
            return
        
        password = getpass.getpass("Password: ")
        if not password:
            print("Password required.")
            self.screen_manager.pause_for_input()
            return
        
        display_name = input("Display name (optional): ").strip() or None
        
        is_admin = input("Make admin? (y/n) [default: n]: ").strip().lower() == 'y'
        
        try:
            # Extract domain from homeserver URL or use configured domain
            server_name = self.base_url.replace('https://', '').replace('http://', '')
            if server_name.startswith('matrix.'):
                server_name = server_name[7:]  # Remove 'matrix.' prefix
            
            user_id = f"@{username}:{server_name}"
            
            user_data = {
                "password": password,
                "admin": is_admin
            }
            
            if display_name:
                user_data["displayname"] = display_name
            
            print(f"\nCreating user: {user_id}")
            
            response = self.make_request('PUT', f'/_synapse/admin/v2/users/{user_id}', user_data)
            
            if response:
                print(f"User created successfully!")
                print(f"  User ID: {user_id}")
                print(f"  Admin: {is_admin}")
            else:
                print("Failed to create user")
                
        except Exception as e:
            print(f"Error creating user: {e}")
            
        self.screen_manager.pause_for_input()

    def deactivate_user(self):
        """Deactivate users with interactive selection."""
        self.screen_manager.show_header("Deactivate User")
        
        print("How would you like to select users to deactivate?")
        print("  1. Select from list (recommended)")
        print("  2. Enter user ID manually")
        print("  0. Cancel")
        
        choice = input("\nSelect option (0-2): ").strip()
        
        if choice == "0":
            return
        elif choice == "1":
            selected_users = self.select_users_for_deactivation()
            if not selected_users:
                print("No users selected.")
                self.screen_manager.pause_for_input()
                return
            
            self.deactivate_selected_users(selected_users)
            
        elif choice == "2":
            user_id = input("Enter user ID (e.g., @username:domain.com): ").strip()
            if not user_id:
                print("User ID required.")
                self.screen_manager.pause_for_input()
                return
            
            # Find the user object for consistency with batch deactivation
            try:
                response = self.make_request('GET', '/_synapse/admin/v2/users')
                all_users = response.get('users', [])
                
                selected_user = None
                for user in all_users:
                    if user['name'] == user_id:
                        selected_user = user
                        break
                
                if selected_user:
                    if selected_user.get('deactivated', False):
                        print("User is already deactivated.")
                        self.screen_manager.pause_for_input()
                        return
                    self.deactivate_selected_users([selected_user])
                else:
                    # Fall back to simple deactivation if user not found in list
                    self.deactivate_single_user_manual(user_id)
                    
            except Exception as e:
                print(f"Error finding user: {e}")
                self.screen_manager.pause_for_input()
        else:
            print("Invalid option.")
            self.screen_manager.pause_for_input()

    def deactivate_selected_users(self, selected_users: List[Dict]):
        """Deactivate the selected users after confirmation."""
        self.screen_manager.show_header("Confirm User Deactivation")
        
        print(f"You have selected {len(selected_users)} user(s) for deactivation:")
        print()
        
        for i, user in enumerate(selected_users, 1):
            user_id = user['name']
            display_name = user.get('displayname', 'No display name')
            role_tag = self.get_user_role_tag(user)
            print(f"{i}. {role_tag} {user_id}")
            print(f"   Display: {display_name}")
            print()
        
        print("⚠️  WARNING: This action cannot be undone!")
        print("Deactivated users will lose access to the server and their sessions will be terminated.")
        confirm = input("Are you sure you want to deactivate these users? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Deactivation cancelled.")
            self.screen_manager.pause_for_input()
            return
        
        # Process deactivations
        successful_deactivations = []
        failed_deactivations = []
        
        for i, user in enumerate(selected_users, 1):
            user_id = user['name']
            display_name = user.get('displayname', 'No display name')
            
            print(f"\n[{i}/{len(selected_users)}] Deactivating: {display_name} ({user_id})")
            
            try:
                deactivate_data = {"deactivated": True}
                
                response = self.make_request('PUT', f'/_synapse/admin/v2/users/{user_id}', deactivate_data)
                
                if response:
                    print(f"✓ User deactivated successfully")
                    successful_deactivations.append(user)
                else:
                    print("✗ Failed to deactivate user")
                    failed_deactivations.append((user, "Unexpected response"))
                    
            except Exception as e:
                print(f"✗ Error: {e}")
                failed_deactivations.append((user, str(e)))
        
        # Show summary
        print(f"\n" + "="*50)
        print("DEACTIVATION SUMMARY")
        print("="*50)
        print(f"Successfully deactivated: {len(successful_deactivations)}")
        print(f"Failed: {len(failed_deactivations)}")
        
        if failed_deactivations:
            print("\nFailed deactivations:")
            for user, error in failed_deactivations:
                user_id = user['name']
                print(f"  - {user_id}: {error}")
        
        self.screen_manager.pause_for_input()

    def deactivate_single_user_manual(self, user_id: str):
        """Deactivate a single user manually (fallback method)."""
        print(f"\nUser to deactivate: {user_id}")
        confirm = input("Are you sure? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Deactivation cancelled.")
            self.screen_manager.pause_for_input()
            return
        
        try:
            deactivate_data = {"deactivated": True}
            
            response = self.make_request('PUT', f'/_synapse/admin/v2/users/{user_id}', deactivate_data)
            
            if response:
                print("User deactivated successfully!")
            else:
                print("Failed to deactivate user")
                
        except Exception as e:
            print(f"Error deactivating user: {e}")
            
        self.screen_manager.pause_for_input()

    # Server Statistics Methods
    def show_server_stats(self):
        """Display server statistics."""
        self.screen_manager.show_header("Server Statistics")
        
        try:
            # Get basic stats
            stats = {}
            
            # User count
            try:
                users_response = self.make_request('GET', '/_synapse/admin/v2/users?limit=1')
                stats['total_users'] = users_response.get('total', 0)
            except:
                stats['total_users'] = 'N/A'
            
            # Room count
            try:
                rooms_response = self.make_request('GET', '/_synapse/admin/v1/rooms?limit=1')
                stats['total_rooms'] = rooms_response.get('total_rooms', 0)
            except:
                stats['total_rooms'] = 'N/A'
            
            # Media statistics
            try:
                media_response = self.make_request('GET', '/_synapse/admin/v1/statistics/users/media')
                if media_response:
                    stats['media_count'] = media_response.get('total_media_length', 0)
                    stats['media_size'] = media_response.get('total_media_size', 0)
                else:
                    stats['media_count'] = 'N/A'
                    stats['media_size'] = 'N/A'
            except:
                stats['media_count'] = 'N/A'
                stats['media_size'] = 'N/A'
            
            print(f"Total Users: {stats['total_users']}")
            print(f"Total Rooms: {stats['total_rooms']}")
            print(f"Media Files: {stats['media_count']}")
            
            if isinstance(stats['media_size'], int):
                size_gb = stats['media_size'] / (1024**3)
                print(f"Media Storage: {size_gb:.2f} GB")
            else:
                print(f"Media Storage: {stats['media_size']}")
                
        except Exception as e:
            print(f"Error retrieving server statistics: {e}")
            
        self.screen_manager.pause_for_input()

    def test_connection_interactive(self):
        """Test connection with user feedback."""
        self.screen_manager.show_header("Test Connection")
        
        print("Testing connection to Matrix server...")
        print(f"Server: {self.base_url}")
        
        if self.test_connection():
            print("Connection test successful!")
        else:
            print("Connection test failed!")
            
        self.screen_manager.pause_for_input()

    # Main Menu
    def show_menu(self):
        """Display the main menu."""
        self.screen_manager.show_header("Matrix Server Administration")
        print("Room Management:")
        print("  1. List all rooms")
        print("  2. Delete room")
        print("  3. Fix room permissions (Element Call)")
        print()
        print("User Management:")
        print("  4. List all users")
        print("  5. Create new user")
        print("  6. Deactivate user")
        print()
        print("Server Information:")
        print("  7. Show server statistics")
        print("  8. Test connection")
        print()
        print("  0. Exit")

    def run(self):
        """Main program loop."""
        self.screen_manager.clear_screen()
        print("Matrix Server Administration Tool")
        print("Using server:", self.base_url)
        
        if not self.test_connection():
            print("Cannot connect to server. Exiting.")
            self.screen_manager.pause_for_input()
            return
        
        while True:
            try:
                self.show_menu()
                choice = input("\nSelect option (0-8): ").strip()
                
                if choice == '0':
                    self.screen_manager.clear_screen()
                    print("Goodbye!")
                    break
                elif choice == '1':
                    self.list_rooms()
                elif choice == '2':
                    self.delete_room()
                elif choice == '3':
                    self.fix_room_permissions()
                elif choice == '4':
                    self.list_users()
                elif choice == '5':
                    self.create_user()
                elif choice == '6':
                    self.deactivate_user()
                elif choice == '7':
                    self.show_server_stats()
                elif choice == '8':
                    self.test_connection_interactive()
                else:
                    self.screen_manager.show_header("Invalid Option")
                    print("Invalid option. Please try again.")
                    self.screen_manager.pause_for_input()
                
            except KeyboardInterrupt:
                self.screen_manager.clear_screen()
                print("\nExiting...")
                break
            except Exception as e:
                self.screen_manager.show_header("Unexpected Error")
                print(f"Unexpected error: {e}")
                self.screen_manager.pause_for_input()


if __name__ == "__main__":
    admin = MatrixAdmin()
    admin.run()
