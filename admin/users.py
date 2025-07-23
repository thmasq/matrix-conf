"""
User management functionality for Matrix administration.
"""

import getpass
from typing import List, Dict

from .core import MatrixClient
from .ui import ScreenManager, TerminalPaginator, FilterSortUI
from .utils import SelectionParser, DataFormatter, ProgressMonitor


class UserManager:
    """Manage Matrix users through the admin API."""
    
    def __init__(self, client: MatrixClient, screen_manager: ScreenManager):
        self.client = client
        self.screen_manager = screen_manager

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

    def get_user_sort_option(self) -> str:
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

    def list_users(self):
        """Enhanced list all users with filtering and sorting."""
        try:
            response = self.client.make_request('GET', '/_synapse/admin/v2/users')
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
                    FilterSortUI.show_filter_sort_status(current_filter, "", current_sort, 
                                                       len(all_users), len(filtered_users), "users")
                    
                    if paginator.needs_pagination():
                        print(f"Page {paginator.current_page + 1} of {paginator.total_pages}")
                    
                    print()
                    
                    # Show users
                    if filtered_users:
                        current_users = paginator.get_current_page_items()
                        start_index = paginator.current_page * paginator.items_per_page + 1
                        
                        for i, user in enumerate(current_users):
                            print(DataFormatter.format_user_info_enhanced(user, start_index + i))
                    else:
                        print("No users match the current filter.")
                    
                    # Show navigation options
                    FilterSortUI.show_navigation_options(paginator.needs_pagination(), bool(filtered_users))
                    
                    choice = FilterSortUI.get_navigation_choice()
                    
                    if choice.lower() == 'q' or choice.lower() == 'quit':
                        return
                    elif choice.lower() == 'f' or choice.lower() == 'filter':
                        new_filter = input("Enter name filter (partial match): ").strip()
                        current_filter = new_filter
                        break  # Refresh display
                    elif choice.lower() == 's' or choice.lower() == 'sort':
                        current_sort = self.get_user_sort_option()
                        break  # Refresh display
                    elif choice.lower() == 'c' or choice.lower() == 'clear':
                        current_filter = ""
                        break  # Refresh display
                    elif choice.lower() == 'r' or choice.lower() == 'reset':
                        current_filter = ""
                        current_sort = "none"
                        break  # Refresh display
                    elif FilterSortUI.handle_pagination_navigation(choice, paginator):
                        continue  # Page changed, refresh display
                    elif choice == '' and not filtered_users:
                        return  # Exit if no users and Enter pressed
                    else:
                        print("Invalid option." if choice else "")
                
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
            server_name = self.client.base_url.replace('https://', '').replace('http://', '')
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
            
            response = self.client.make_request('PUT', f'/_synapse/admin/v2/users/{user_id}', user_data)
            
            if response:
                print(f"User created successfully!")
                print(f"  User ID: {user_id}")
                print(f"  Admin: {is_admin}")
            else:
                print("Failed to create user")
                
        except Exception as e:
            print(f"Error creating user: {e}")
            
        self.screen_manager.pause_for_input()

    def select_users_for_deactivation(self) -> List[Dict]:
        """Show user list and allow user to select users for deactivation."""
        try:
            response = self.client.make_request('GET', '/_synapse/admin/v2/users')
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
                    FilterSortUI.show_filter_sort_status(current_filter, "", current_sort, 
                                                       len(active_users), len(filtered_users), "users")
                    
                    if paginator.needs_pagination():
                        print(f"Page {paginator.current_page + 1} of {paginator.total_pages}")
                    
                    print()
                    
                    # Show users
                    if filtered_users:
                        current_users = paginator.get_current_page_items()
                        start_index = paginator.get_current_page_start_index()
                        
                        for i, user in enumerate(current_users):
                            global_index = start_index + i
                            print(DataFormatter.format_user_info_enhanced(user, global_index))
                    else:
                        print("No users match the current filter.")
                    
                    # Show selection instructions
                    if filtered_users:
                        print("\nSelection:")
                        examples = SelectionParser.format_selection_examples(len(filtered_users))
                        print(f"  Enter numbers to deactivate: {examples}")
                        print("  Or use navigation/filter options below")
                    
                    FilterSortUI.show_navigation_options(paginator.needs_pagination(), bool(filtered_users))
                    
                    choice = FilterSortUI.get_navigation_choice()
                    
                    if choice.lower() == 'q' or choice.lower() == 'quit':
                        return []
                    elif choice.lower() == 'f' or choice.lower() == 'filter':
                        new_filter = input("Enter name filter (partial match): ").strip()
                        current_filter = new_filter
                        break  # Refresh display
                    elif choice.lower() == 's' or choice.lower() == 'sort':
                        current_sort = self.get_user_sort_option()
                        break  # Refresh display
                    elif choice.lower() == 'c' or choice.lower() == 'clear':
                        current_filter = ""
                        break  # Refresh display
                    elif choice.lower() == 'r' or choice.lower() == 'reset':
                        current_filter = ""
                        current_sort = "none"
                        break  # Refresh display
                    elif FilterSortUI.handle_pagination_navigation(choice, paginator):
                        continue  # Page changed, refresh display
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
                
        except Exception as e:
            self.screen_manager.show_header("Deactivate Users")
            print(f"Error loading users: {e}")
            self.screen_manager.pause_for_input()
            return []

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
                response = self.client.make_request('GET', '/_synapse/admin/v2/users')
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
            role_tag = DataFormatter.get_user_role_tag(user)
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
            
            ProgressMonitor.show_progress(i, len(selected_users), f"{display_name} ({user_id})")
            
            try:
                deactivate_data = {"deactivated": True}
                
                response = self.client.make_request('PUT', f'/_synapse/admin/v2/users/{user_id}', deactivate_data)
                
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
        ProgressMonitor.show_operation_summary("DEACTIVATION", len(successful_deactivations), len(failed_deactivations), failed_deactivations)
        
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
            
            response = self.client.make_request('PUT', f'/_synapse/admin/v2/users/{user_id}', deactivate_data)
            
            if response:
                print("User deactivated successfully!")
            else:
                print("Failed to deactivate user")
                
        except Exception as e:
            print(f"Error deactivating user: {e}")
            
        self.screen_manager.pause_for_input()
