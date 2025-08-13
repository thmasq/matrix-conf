"""Main application class that orchestrates all Matrix administration functionality."""

import sys

from .core import ConfigManager, MatrixClient
from .rooms import RoomManager
from .stats import StatsManager
from .tokens import TokenManager  # Add this import
from .ui import ScreenManager
from .users import UserManager


class MatrixAdminApp:
    """Main Matrix administration application."""

    def __init__(self) -> None:
        self.screen_manager = ScreenManager()
        self.config = ConfigManager.load_config()

        # Initialize Matrix client
        self.client = MatrixClient(
            base_url=self.config.get("homeserver_url", ""),
            admin_token=self.config.get("admin_token", ""),
        )

        # Initialize managers
        self.room_manager = RoomManager(self.client, self.screen_manager)
        self.user_manager = UserManager(self.client, self.screen_manager)
        self.stats_manager = StatsManager(self.client, self.screen_manager)
        self.token_manager = TokenManager(
            self.client, self.screen_manager
        )  # Add this line

        # Setup configuration if needed
        if not self.client.base_url or not self.client.admin_token:
            if not ConfigManager.setup_config_interactive(self.client):
                sys.exit(1)

    def show_menu(self) -> None:
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
        print("Registration Tokens:")
        print("  7. Create registration tokens (batch)")
        print("  8. List registration tokens")
        print("  9. Export existing tokens to file")
        print(" 10. Delete registration token")
        print()
        print("Server Information:")
        print(" 11. Show server statistics")
        print(" 12. Test connection")
        print(" 13. Server information")
        print()
        print("  0. Exit")

    def handle_menu_choice(self, choice: str) -> bool:
        """Handle menu choice. Returns False if should exit."""
        try:
            if choice == "0":
                self.screen_manager.clear_screen()
                print("Goodbye!")
                return False
            if choice == "1":
                self.room_manager.list_rooms()
            elif choice == "2":
                self.room_manager.delete_room()
            elif choice == "3":
                self.room_manager.fix_room_permissions()
            elif choice == "4":
                self.user_manager.list_users()
            elif choice == "5":
                self.user_manager.create_user()
            elif choice == "6":
                self.user_manager.deactivate_user()
            elif choice == "7":
                self.token_manager.create_registration_token()
            elif choice == "8":
                self.token_manager.list_registration_tokens()
            elif choice == "9":
                self.token_manager.export_existing_tokens()
            elif choice == "10":
                self.token_manager.delete_registration_token()
            elif choice == "11":
                self.stats_manager.show_server_stats()
            elif choice == "12":
                self.stats_manager.test_connection_interactive()
            elif choice == "13":
                self.stats_manager.show_server_info()
            else:
                self.screen_manager.show_header("Invalid Option")
                print("Invalid option. Please try again.")
                self.screen_manager.pause_for_input()

            return True

        except Exception as e:
            self.screen_manager.show_header("Unexpected Error")
            print(f"Unexpected error: {e}")
            self.screen_manager.pause_for_input()
            return True

    def run(self) -> None:
        """Main program loop."""
        self.screen_manager.clear_screen()
        print("Matrix Server Administration Tool")
        print("Using server:", self.client.base_url)

        # Test initial connection
        if not self.client.test_connection():
            print("Cannot connect to server. Exiting.")
            self.screen_manager.pause_for_input()
            return

        # Main loop
        while True:
            try:
                self.show_menu()
                choice = input("\nSelect option (0-13): ").strip()

                if not self.handle_menu_choice(choice):
                    break

            except KeyboardInterrupt:
                self.screen_manager.clear_screen()
                print("\nExiting...")
                break
            except Exception as e:
                self.screen_manager.show_header("Unexpected Error")
                print(f"Unexpected error in main loop: {e}")
                self.screen_manager.pause_for_input()
