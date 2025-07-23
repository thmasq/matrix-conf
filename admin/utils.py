"""
Utility classes and functions for the Matrix administration tool.
"""

from typing import List


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


class DataFormatter:
    """Format data for display in the terminal interface."""
    
    @staticmethod
    def format_room_info(room: dict, index: int) -> str:
        """Format room information for display."""
        alias = room.get('canonical_alias', 'No alias')
        name = room.get('name', 'Unnamed room')
        members = room.get('joined_members', 0)
        
        return f"{index:3d}. Room: {name}\n" \
               f"     ID: {room['room_id']}\n" \
               f"     Alias: {alias}\n" \
               f"     Members: {members}\n"

    @staticmethod
    def format_room_info_enhanced(room: dict, index: int) -> str:
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

    @staticmethod
    def format_user_info(user: dict, index: int) -> str:
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

    @staticmethod
    def format_user_info_enhanced(user: dict, index: int) -> str:
        """Enhanced format user information for display with role tags."""
        user_id = user['name']
        display_name = user.get('displayname', 'No display name')
        role_tag = DataFormatter.get_user_role_tag(user)
        
        return f"{index:3d}. {role_tag} {user_id}\n" \
               f"     Display: {display_name}\n"

    @staticmethod
    def get_user_role_tag(user: dict) -> str:
        """Get a colored role tag for the user."""
        is_admin = user.get('admin', False)
        is_deactivated = user.get('deactivated', False)
        
        if is_deactivated:
            return "🚫 DEACTIVATED"
        elif is_admin:
            return "👑 ADMIN"
        else:
            return "👤 USER"


class ProgressMonitor:
    """Monitor and display progress for long-running operations."""
    
    @staticmethod
    def show_operation_summary(operation_name: str, successful: int, failed: int, failed_items: List = None):
        """Show a summary of a batch operation."""
        print(f"\n" + "="*50)
        print(f"{operation_name.upper()} SUMMARY")
        print("="*50)
        print(f"Successfully completed: {successful}")
        print(f"Failed: {failed}")
        
        if failed_items:
            print(f"\nFailed {operation_name.lower()}s:")
            for item, error in failed_items:
                item_name = item.get('name', item.get('room_id', 'Unknown'))
                print(f"  - {item_name}: {error}")

    @staticmethod
    def show_progress(current: int, total: int, item_name: str):
        """Show progress for current operation."""
        print(f"\n[{current}/{total}] Processing: {item_name}")
