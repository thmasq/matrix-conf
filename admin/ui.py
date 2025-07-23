"""
User interface components for terminal-based administration.
"""

import shutil
from typing import List, Any


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


class FilterSortUI:
    """UI components for filtering and sorting operations."""
    
    @staticmethod
    def show_filter_sort_status(current_filter: str, current_filter_type: str, 
                              current_sort: str, total_items: int, filtered_count: int,
                              item_type: str = "items"):
        """Display current filter and sort status."""
        print(f"{item_type.title()}: {filtered_count}/{total_items}")
        
        if current_filter:
            if current_filter_type:
                filter_type_names = {
                    "name": "Name",
                    "alias": "Alias", 
                    "id": "ID",
                    "any": "Any field",
                    "members": "Member count"
                }
                filter_type_display = filter_type_names.get(current_filter_type, current_filter_type)
                print(f"Filter: '{current_filter}' ({filter_type_display})")
            else:
                print(f"Filter: '{current_filter}'")
        
        if current_sort != "none":
            print(f"Sort: {current_sort}")

    @staticmethod
    def get_navigation_choice() -> str:
        """Get navigation choice from user."""
        try:
            return input("\nAction: ").strip()
        except KeyboardInterrupt:
            return 'q'

    @staticmethod
    def handle_pagination_navigation(choice: str, paginator: TerminalPaginator) -> bool:
        """Handle pagination navigation commands. Returns True if page changed."""
        choice = choice.lower()
        
        if choice == '' or choice == 'n' or choice == 'next':
            if paginator.needs_pagination():
                if paginator.current_page < paginator.total_pages - 1:
                    paginator.current_page += 1
                    return True
                else:
                    print("Already on last page.")
            return False
        elif choice == 'p' or choice == 'prev' or choice == 'previous':
            if paginator.needs_pagination() and paginator.current_page > 0:
                paginator.current_page -= 1
                return True
            else:
                print("Already on first page." if paginator.needs_pagination() else "Invalid option.")
            return False
        elif choice == 'g' or choice == 'goto':
            if paginator.needs_pagination():
                try:
                    page_num = int(input(f"Go to page (1-{paginator.total_pages}): ")) - 1
                    if 0 <= page_num < paginator.total_pages:
                        paginator.current_page = page_num
                        return True
                    else:
                        print(f"Page must be between 1 and {paginator.total_pages}")
                except ValueError:
                    print("Invalid page number.")
            else:
                print("No pagination available.")
            return False
        
        return False

    @staticmethod
    def show_navigation_options(has_pagination: bool, has_items: bool):
        """Show available navigation options."""
        if has_pagination and has_items:
            print("\nNavigation:")
            print("  [Enter] Next page  [p] Previous page  [g] Go to page")
            print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Cancel/Quit")
        else:
            print("\nOptions:")
            print("  [f] Filter  [s] Sort  [c] Clear filter  [r] Reset  [q] Cancel/Quit")
            if not has_items:
                print("  [Enter] Continue")
