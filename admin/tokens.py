"""Registration token management functionality for Matrix administration."""

import secrets
from datetime import datetime, timedelta

from .core import MatrixClient
from .ui import FilterSortUI, ScreenManager, TerminalPaginator
from .utils import DataFormatter, ProgressMonitor, SelectionParser


class TokenManager:
    """Manage Matrix registration tokens through the admin API."""

    def __init__(self, client: MatrixClient, screen_manager: ScreenManager) -> None:
        self.client = client
        self.screen_manager = screen_manager

    def create_registration_token(self) -> None:
        """Create registration tokens interactively with batch support."""
        self.screen_manager.show_header("Create Registration Tokens")

        print("Token Configuration:")
        
        # Get number of tokens to create
        while True:
            try:
                count_input = input("Number of tokens to create (default: 1): ").strip()
                token_count = int(count_input) if count_input else 1
                if token_count < 1:
                    print("Must create at least 1 token.")
                    continue
                break
            except ValueError:
                print("Invalid number. Please enter a positive integer.")

        # Get number of uses per token
        while True:
            try:
                uses_input = input("Number of uses allowed per token (default: 1): ").strip()
                uses_allowed = int(uses_input) if uses_input else 1
                if uses_allowed < 1:
                    print("Must allow at least 1 use.")
                    continue
                break
            except ValueError:
                print("Invalid number. Please enter a positive integer.")

        # Get expiration
        print("\nExpiration options:")
        print("  1. Never expires")
        print("  2. 1 day")
        print("  3. 1 week") 
        print("  4. 1 month")
        print("  5. Custom")

        while True:
            choice = input("Select expiration (1-5): ").strip()
            expiry_time = None
            expiry_description = ""
            
            if choice == "1":
                expiry_time = None
                expiry_description = "Never"
                break
            elif choice == "2":
                expiry_time = int((datetime.now() + timedelta(days=1)).timestamp() * 1000)
                expiry_description = "1 day"
                break
            elif choice == "3":
                expiry_time = int((datetime.now() + timedelta(weeks=1)).timestamp() * 1000)
                expiry_description = "1 week"
                break
            elif choice == "4":
                expiry_time = int((datetime.now() + timedelta(days=30)).timestamp() * 1000)
                expiry_description = "1 month"
                break
            elif choice == "5":
                try:
                    days = int(input("Enter number of days until expiration: "))
                    expiry_time = int((datetime.now() + timedelta(days=days)).timestamp() * 1000)
                    expiry_description = f"{days} days"
                    break
                except ValueError:
                    print("Invalid number of days.")
            else:
                print("Invalid choice. Please select 1-5.")

        # Get output filename
        default_filename = f"registration_tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filename = input(f"Output filename (default: {default_filename}): ").strip()
        if not filename:
            filename = default_filename

        # Summary
        print(f"\nSummary:")
        print(f"  Tokens to create: {token_count}")
        print(f"  Uses per token: {uses_allowed}")
        print(f"  Expiration: {expiry_description}")
        print(f"  Output file: {filename}")
        
        confirm = input("\nProceed with token creation? (yes/no): ").strip().lower()
        if confirm != "yes":
            print("Token creation cancelled.")
            self.screen_manager.pause_for_input()
            return

        # Generate tokens
        print(f"\nGenerating {token_count} registration tokens...")
        
        successful_tokens = []
        failed_tokens = []
        
        for i in range(token_count):
            try:
                # Generate unique token
                token = secrets.token_urlsafe(32)
                
                print(f"Creating token {i+1}/{token_count}... ", end="", flush=True)
                
                token_data = {
                    "token": token,
                    "uses_allowed": uses_allowed,
                    "expiry_time": expiry_time
                }

                response = self.client.make_request(
                    "POST",
                    "/_synapse/admin/v1/registration_tokens/new",
                    token_data,
                )

                if response:
                    successful_tokens.append({
                        "token": token,
                        "uses_allowed": uses_allowed,
                        "expiry_time": expiry_time,
                        "expiry_description": expiry_description
                    })
                    print("✓")
                else:
                    failed_tokens.append(f"Token {i+1}: Unknown error")
                    print("✗")

            except Exception as e:
                failed_tokens.append(f"Token {i+1}: {str(e)}")
                print(f"✗ ({str(e)})")

        # Save successful tokens to file
        if successful_tokens:
            try:
                with open(filename, 'w') as f:
                    f.write("Matrix Registration Tokens\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Server: {self.client.base_url}\n")
                    f.write(f"Uses per token: {uses_allowed}\n")
                    f.write(f"Expiration: {expiry_description}\n")
                    f.write(f"Total tokens: {len(successful_tokens)}\n")
                    f.write("\n")
                    
                    for i, token_info in enumerate(successful_tokens, 1):
                        f.write(f"Token {i}: {token_info['token']}\n")
                    
                    f.write("\n" + "=" * 50 + "\n")
                    f.write("SECURITY NOTES:\n")
                    f.write("- Keep these tokens secure - anyone with a token can register\n")
                    f.write("- Share only with trusted users\n")
                    f.write("- Monitor token usage through the admin interface\n")
                    f.write("- Delete unused tokens when no longer needed\n")

                print(f"\nTokens saved to: {filename}")
                
            except Exception as e:
                print(f"\nError saving tokens to file: {e}")
                print("Tokens were created but not saved to file.")

        # Show summary
        print("\n" + "="*50)
        print("TOKEN CREATION SUMMARY")
        print("="*50)
        print(f"Successfully created: {len(successful_tokens)}")
        print(f"Failed: {len(failed_tokens)}")

        if successful_tokens:
            print(f"\nExample token:")
            print(f"{successful_tokens[0]['token']}")
            
        if failed_tokens:
            print(f"\nFailed tokens:")
            for failure in failed_tokens:
                print(f"  - {failure}")

        print(f"\nAll successful tokens saved to: {filename}")
        print("⚠️  Keep the token file secure - treat it like a password file!")

        self.screen_manager.pause_for_input()

    def list_registration_tokens(self) -> None:
        """List all registration tokens."""
        try:
            response = self.client.make_request(
                "GET", 
                "/_synapse/admin/v1/registration_tokens"
            )
            
            tokens = response.get("registration_tokens", [])
            
            self.screen_manager.show_header("Registration Tokens")
            
            if not tokens:
                print("No registration tokens found.")
                self.screen_manager.pause_for_input()
                return

            print(f"Found {len(tokens)} registration token(s):\n")
            
            for i, token in enumerate(tokens, 1):
                token_str = token["token"]
                uses_allowed = token.get("uses_allowed")
                completed = token.get("completed", 0)
                pending = token.get("pending", 0)
                expiry_time = token.get("expiry_time")
                
                print(f"{i}. Token: {token_str}")
                
                if uses_allowed is None:
                    print("   Uses: Unlimited")
                else:
                    remaining = uses_allowed - completed - pending
                    print(f"   Uses: {completed} completed, {pending} pending, {remaining} remaining")
                
                if expiry_time:
                    expiry_date = datetime.fromtimestamp(expiry_time / 1000)
                    now = datetime.now()
                    if expiry_date < now:
                        print(f"   Status: ⚠️ EXPIRED ({expiry_date.strftime('%Y-%m-%d %H:%M')})")
                    else:
                        print(f"   Expires: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    print("   Expires: Never")
                
                print()

        except Exception as e:
            self.screen_manager.show_header("Registration Tokens")
            print(f"Error listing tokens: {e}")

        self.screen_manager.pause_for_input()

    def export_existing_tokens(self) -> None:
        """Export existing registration tokens to a file."""
        try:
            response = self.client.make_request(
                "GET", 
                "/_synapse/admin/v1/registration_tokens"
            )
            
            tokens = response.get("registration_tokens", [])
            
            self.screen_manager.show_header("Export Registration Tokens")
            
            if not tokens:
                print("No registration tokens found to export.")
                self.screen_manager.pause_for_input()
                return

            # Filter options
            print("Export options:")
            print("  1. All tokens")
            print("  2. Active tokens only (not expired, has remaining uses)")
            print("  3. Unused tokens only (never used)")
            
            while True:
                choice = input("Select export type (1-3): ").strip()
                
                if choice == "1":
                    filtered_tokens = tokens
                    filter_description = "all tokens"
                    break
                elif choice == "2":
                    filtered_tokens = []
                    now = datetime.now()
                    for token in tokens:
                        # Check if not expired
                        expiry_time = token.get("expiry_time")
                        is_expired = False
                        if expiry_time:
                            expiry_date = datetime.fromtimestamp(expiry_time / 1000)
                            is_expired = expiry_date < now
                        
                        # Check if has remaining uses
                        uses_allowed = token.get("uses_allowed")
                        completed = token.get("completed", 0)
                        pending = token.get("pending", 0)
                        
                        has_remaining_uses = True
                        if uses_allowed is not None:
                            remaining = uses_allowed - completed - pending
                            has_remaining_uses = remaining > 0
                        
                        if not is_expired and has_remaining_uses:
                            filtered_tokens.append(token)
                    
                    filter_description = "active tokens only"
                    break
                elif choice == "3":
                    filtered_tokens = [
                        token for token in tokens 
                        if token.get("completed", 0) == 0 and token.get("pending", 0) == 0
                    ]
                    filter_description = "unused tokens only"
                    break
                else:
                    print("Invalid choice. Please select 1-3.")

            if not filtered_tokens:
                print(f"No tokens match the selected criteria ({filter_description}).")
                self.screen_manager.pause_for_input()
                return

            # Get output filename
            default_filename = f"exported_tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filename = input(f"Output filename (default: {default_filename}): ").strip()
            if not filename:
                filename = default_filename

            print(f"\nExporting {len(filtered_tokens)} tokens ({filter_description})...")

            try:
                with open(filename, 'w') as f:
                    f.write("Matrix Registration Tokens (Exported)\n")
                    f.write("=" * 50 + "\n")
                    f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Server: {self.client.base_url}\n")
                    f.write(f"Filter: {filter_description}\n")
                    f.write(f"Total tokens: {len(filtered_tokens)}\n")
                    f.write("\n")
                    
                    for i, token_info in enumerate(filtered_tokens, 1):
                        token = token_info["token"]
                        uses_allowed = token_info.get("uses_allowed")
                        completed = token_info.get("completed", 0)
                        pending = token_info.get("pending", 0)
                        expiry_time = token_info.get("expiry_time")
                        
                        f.write(f"Token {i}: {token}\n")
                        
                        if uses_allowed is None:
                            f.write(f"  Uses: Unlimited (completed: {completed}, pending: {pending})\n")
                        else:
                            remaining = uses_allowed - completed - pending
                            f.write(f"  Uses: {remaining} remaining ({completed} completed, {pending} pending)\n")
                        
                        if expiry_time:
                            expiry_date = datetime.fromtimestamp(expiry_time / 1000)
                            status = " [EXPIRED]" if expiry_date < datetime.now() else ""
                            f.write(f"  Expires: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}{status}\n")
                        else:
                            f.write(f"  Expires: Never\n")
                        
                        f.write("\n")
                    
                    f.write("\n" + "=" * 50 + "\n")
                    f.write("SECURITY NOTES:\n")
                    f.write("- Keep these tokens secure - anyone with a token can register\n")
                    f.write("- Share only with trusted users\n")
                    f.write("- Monitor token usage through the admin interface\n")
                    f.write("- Delete unused tokens when no longer needed\n")

                print(f"✓ Tokens exported successfully to: {filename}")
                
            except Exception as e:
                print(f"Error saving tokens to file: {e}")

        except Exception as e:
            print(f"Error exporting tokens: {e}")

        self.screen_manager.pause_for_input()

    def select_tokens_for_deletion(self) -> list[dict]:
        """Show token list and allow user to select tokens for deletion."""
        try:
            response = self.client.make_request(
                "GET",
                "/_synapse/admin/v1/registration_tokens"
            )
            
            all_tokens = response.get("registration_tokens", [])
            
            if not all_tokens:
                self.screen_manager.show_header("Delete Registration Tokens")
                print("No registration tokens found.")
                self.screen_manager.pause_for_input()
                return []

            # Handle pagination
            paginator = TerminalPaginator(all_tokens, self.screen_manager)

            # Display tokens
            while True:
                self.screen_manager.show_header("Delete Registration Tokens - Select from List")

                print(f"Total tokens: {len(all_tokens)}")

                if paginator.needs_pagination():
                    print(f"Page {paginator.current_page + 1} of {paginator.total_pages}")

                print()

                # Show tokens
                current_tokens = paginator.get_current_page_items()
                start_index = paginator.get_current_page_start_index()

                for i, token in enumerate(current_tokens):
                    global_index = start_index + i
                    print(self.format_token_for_selection(token, global_index))

                # Show selection instructions
                print("\nSelection:")
                examples = SelectionParser.format_selection_examples(len(all_tokens))
                print(f"  Enter numbers to delete: {examples}")
                print("  Or use navigation options below")

                # Show navigation options
                if paginator.needs_pagination():
                    print("\nNavigation:")
                    print("  [Enter] Next page  [p] Previous page  [g] Go to page  [q] Cancel")
                else:
                    print("\nOptions:")
                    print("  [q] Cancel")

                choice = input("\nAction: ").strip()

                if choice.lower() == "q" or choice.lower() == "quit":
                    return []
                
                # Handle pagination
                if FilterSortUI.handle_pagination_navigation(choice, paginator):
                    continue  # Page changed, refresh display
                
                # Try to parse as selection
                try:
                    selected_indices = SelectionParser.parse_selection(choice, len(all_tokens))
                    if not selected_indices:
                        print("No valid selection made.")
                        continue

                    # Get selected tokens
                    selected_tokens = []
                    for idx in selected_indices:
                        selected_tokens.append(all_tokens[idx - 1])  # Convert to 0-based

                    return selected_tokens

                except ValueError as e:
                    print(f"Invalid selection: {e}")
                    print("Use navigation commands or enter valid numbers/ranges.")

        except Exception as e:
            self.screen_manager.show_header("Delete Registration Tokens")
            print(f"Error loading tokens: {e}")
            self.screen_manager.pause_for_input()
            return []

    def format_token_for_selection(self, token: dict, index: int) -> str:
        """Format token information for selection display."""
        token_str = token["token"]
        uses_allowed = token.get("uses_allowed")
        completed = token.get("completed", 0)
        pending = token.get("pending", 0)
        expiry_time = token.get("expiry_time")
        
        # Calculate remaining uses
        if uses_allowed is None:
            uses_display = f"∞ uses ({completed} used)"
        else:
            remaining = uses_allowed - completed - pending
            uses_display = f"{remaining} remaining ({completed} used, {pending} pending)"
        
        # Format expiry
        expiry_display = ""
        if expiry_time:
            expiry_date = datetime.fromtimestamp(expiry_time / 1000)
            if expiry_date < datetime.now():
                expiry_display = f" [EXPIRED {expiry_date.strftime('%m/%d')}]"
            else:
                expiry_display = f" [expires {expiry_date.strftime('%m/%d')}]"
        else:
            expiry_display = " [never expires]"
        
        # Show abbreviated token for readability
        token_display = f"{token_str[:12]}...{token_str[-8:]}"
        
        return f"{index:3d}. {token_display} - {uses_display}{expiry_display}"

    def delete_registration_token(self) -> None:
        """Delete registration tokens with interactive selection."""
        self.screen_manager.show_header("Delete Registration Tokens")

        print("How would you like to select tokens to delete?")
        print("  1. Select from list (recommended)")
        print("  2. Enter token string manually")
        print("  0. Cancel")

        choice = input("\nSelect option (0-2): ").strip()

        if choice == "0":
            return
        elif choice == "1":
            selected_tokens = self.select_tokens_for_deletion()
            if not selected_tokens:
                print("No tokens selected.")
                self.screen_manager.pause_for_input()
                return

            self.delete_selected_tokens(selected_tokens)

        elif choice == "2":
            token_input = input("Enter full token string: ").strip()
            if not token_input:
                print("No token specified.")
                self.screen_manager.pause_for_input()
                return

            # Find the token object for consistency with batch deletion
            try:
                response = self.client.make_request(
                    "GET",
                    "/_synapse/admin/v1/registration_tokens"
                )
                all_tokens = response.get("registration_tokens", [])

                selected_token = None
                for token in all_tokens:
                    if token["token"] == token_input:
                        selected_token = token
                        break

                if selected_token:
                    self.delete_selected_tokens([selected_token])
                else:
                    print("Token not found.")
                    self.screen_manager.pause_for_input()

            except Exception as e:
                print(f"Error finding token: {e}")
                self.screen_manager.pause_for_input()
        else:
            print("Invalid option.")
            self.screen_manager.pause_for_input()

    def delete_selected_tokens(self, selected_tokens: list[dict]) -> None:
        """Delete the selected tokens after confirmation."""
        self.screen_manager.show_header("Confirm Token Deletion")

        print(f"You have selected {len(selected_tokens)} token(s) for deletion:")
        print()

        for i, token in enumerate(selected_tokens, 1):
            token_str = token["token"]
            uses_allowed = token.get("uses_allowed")
            completed = token.get("completed", 0)
            pending = token.get("pending", 0)
            expiry_time = token.get("expiry_time")
            
            print(f"{i}. {token_str[:16]}...{token_str[-8:]}")
            
            if uses_allowed is None:
                print(f"   Uses: Unlimited ({completed} completed, {pending} pending)")
            else:
                remaining = uses_allowed - completed - pending
                print(f"   Uses: {remaining} remaining ({completed} completed, {pending} pending)")
            
            if expiry_time:
                expiry_date = datetime.fromtimestamp(expiry_time / 1000)
                status = " (EXPIRED)" if expiry_date < datetime.now() else ""
                print(f"   Expires: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}{status}")
            else:
                print("   Expires: Never")
            print()

        print("⚠️  WARNING: This action cannot be undone!")
        confirm = (
            input("Are you sure you want to delete these tokens? (yes/no): ")
            .strip()
            .lower()
        )

        if confirm != "yes":
            print("Deletion cancelled.")
            self.screen_manager.pause_for_input()
            return

        # Process deletions
        successful_deletions = []
        failed_deletions = []

        for i, token in enumerate(selected_tokens, 1):
            token_str = token["token"]
            token_display = f"{token_str[:12]}...{token_str[-8:]}"

            ProgressMonitor.show_progress(i, len(selected_tokens), token_display)

            try:
                response = self.client.make_request(
                    "DELETE",
                    f"/_synapse/admin/v1/registration_tokens/{token_str}"
                )

                print("✓ Token deleted successfully")
                successful_deletions.append(token)

            except Exception as e:
                print(f"✗ Error: {e}")
                failed_deletions.append((token, str(e)))

        # Show summary
        ProgressMonitor.show_operation_summary(
            "DELETION",
            len(successful_deletions),
            len(failed_deletions),
            [({"name": t["token"][:16] + "..."}, err) for t, err in failed_deletions],
        )

        self.screen_manager.pause_for_input()
