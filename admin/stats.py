"""
Server statistics and monitoring functionality for Matrix administration.
"""

from .core import MatrixClient
from .ui import ScreenManager


class StatsManager:
    """Manage server statistics and monitoring."""
    
    def __init__(self, client: MatrixClient, screen_manager: ScreenManager):
        self.client = client
        self.screen_manager = screen_manager

    def show_server_stats(self):
        """Display server statistics."""
        self.screen_manager.show_header("Server Statistics")
        
        try:
            # Get basic stats
            stats = {}
            
            # User count
            try:
                users_response = self.client.make_request('GET', '/_synapse/admin/v2/users?limit=1')
                stats['total_users'] = users_response.get('total', 0)
            except:
                stats['total_users'] = 'N/A'
            
            # Room count
            try:
                rooms_response = self.client.make_request('GET', '/_synapse/admin/v1/rooms?limit=1')
                stats['total_rooms'] = rooms_response.get('total_rooms', 0)
            except:
                stats['total_rooms'] = 'N/A'
            
            # Media statistics
            try:
                media_response = self.client.make_request('GET', '/_synapse/admin/v1/statistics/users/media')
                if media_response:
                    stats['media_count'] = media_response.get('total_media_length', 0)
                    stats['media_size'] = media_response.get('total_media_size', 0)
                else:
                    stats['media_count'] = 'N/A'
                    stats['media_size'] = 'N/A'
            except:
                stats['media_count'] = 'N/A'
                stats['media_size'] = 'N/A'
            
            # Display stats
            print(f"Total Users: {stats['total_users']}")
            print(f"Total Rooms: {stats['total_rooms']}")
            print(f"Media Files: {stats['media_count']}")
            
            if isinstance(stats['media_size'], int):
                size_gb = stats['media_size'] / (1024**3)
                print(f"Media Storage: {size_gb:.2f} GB")
            else:
                print(f"Media Storage: {stats['media_size']}")
            
            # Try to get additional statistics
            self._show_detailed_stats()
                
        except Exception as e:
            print(f"Error retrieving server statistics: {e}")
            
        self.screen_manager.pause_for_input()

    def _show_detailed_stats(self):
        """Show detailed server statistics if available."""
        try:
            print("\n" + "="*40)
            print("DETAILED STATISTICS")
            print("="*40)
            
            # User activity breakdown
            try:
                users_response = self.client.make_request('GET', '/_synapse/admin/v2/users?limit=1000')
                all_users = users_response.get('users', [])
                
                if all_users:
                    active_users = [u for u in all_users if not u.get('deactivated', False)]
                    admin_users = [u for u in all_users if u.get('admin', False)]
                    deactivated_users = [u for u in all_users if u.get('deactivated', False)]
                    
                    print(f"Active Users: {len(active_users)}")
                    print(f"Admin Users: {len(admin_users)}")
                    print(f"Deactivated Users: {len(deactivated_users)}")
            except:
                print("User breakdown: N/A")
            
            # Room activity breakdown
            try:
                rooms_response = self.client.make_request('GET', '/_synapse/admin/v1/rooms?limit=1000')
                all_rooms = rooms_response.get('rooms', [])
                
                if all_rooms:
                    empty_rooms = [r for r in all_rooms if r.get('joined_members', 0) == 0]
                    small_rooms = [r for r in all_rooms if 1 <= r.get('joined_members', 0) <= 5]
                    medium_rooms = [r for r in all_rooms if 6 <= r.get('joined_members', 0) <= 20]
                    large_rooms = [r for r in all_rooms if r.get('joined_members', 0) > 20]
                    
                    print(f"Empty Rooms: {len(empty_rooms)}")
                    print(f"Small Rooms (1-5 members): {len(small_rooms)}")
                    print(f"Medium Rooms (6-20 members): {len(medium_rooms)}")
                    print(f"Large Rooms (20+ members): {len(large_rooms)}")
                    
                    # Calculate average room size
                    total_members = sum(r.get('joined_members', 0) for r in all_rooms)
                    avg_room_size = total_members / len(all_rooms) if all_rooms else 0
                    print(f"Average Room Size: {avg_room_size:.1f} members")
            except:
                print("Room breakdown: N/A")
            
        except Exception as e:
            print(f"Error retrieving detailed statistics: {e}")

    def test_connection_interactive(self):
        """Test connection with user feedback."""
        self.screen_manager.show_header("Test Connection")
        
        print("Testing connection to Matrix server...")
        print(f"Server: {self.client.base_url}")
        
        if self.client.test_connection():
            print("Connection test successful!")
            
            # Test admin privileges
            try:
                # Try to access admin endpoint
                response = self.client.make_request('GET', '/_synapse/admin/v1/server_version')
                if response:
                    print("Admin privileges: ✓ Confirmed")
                    if 'server_version' in response:
                        print(f"Synapse Version: {response['server_version']}")
                else:
                    print("Admin privileges: ✗ Limited access")
            except Exception as e:
                print(f"Admin privileges: ✗ Error testing admin access: {e}")
        else:
            print("Connection test failed!")
            print("\nTroubleshooting:")
            print("1. Check that the homeserver URL is correct")
            print("2. Verify the admin token is valid")
            print("3. Ensure the Matrix server is running")
            print("4. Check network connectivity")
            
        self.screen_manager.pause_for_input()

    def show_server_info(self):
        """Show general server information."""
        self.screen_manager.show_header("Server Information")
        
        try:
            print(f"Homeserver URL: {self.client.base_url}")
            
            # Try to get server version
            try:
                version_response = self.client.make_request('GET', '/_synapse/admin/v1/server_version')
                if version_response and 'server_version' in version_response:
                    print(f"Synapse Version: {version_response['server_version']}")
            except:
                print("Synapse Version: Unable to retrieve")
            
            # Try to get current admin user
            try:
                whoami_response = self.client.make_request('GET', '/_matrix/client/r0/account/whoami')
                if whoami_response and 'user_id' in whoami_response:
                    print(f"Connected as: {whoami_response['user_id']}")
            except:
                print("Connected as: Unable to retrieve")
            
            # Test various endpoints
            print("\nEndpoint Status:")
            self._test_endpoint_status()
            
        except Exception as e:
            print(f"Error retrieving server information: {e}")
        
        self.screen_manager.pause_for_input()

    def _test_endpoint_status(self):
        """Test the status of various Matrix endpoints."""
        endpoints = [
            ("Client API", "/_matrix/client/versions"),
            ("Admin API", "/_synapse/admin/v1/server_version"),
            ("Federation", "/_matrix/federation/v1/version"),
            ("User Directory", "/_matrix/client/r0/user_directory/search")
        ]
        
        for name, endpoint in endpoints:
            try:
                response = self.client.make_request('GET', endpoint)
                if response:
                    print(f"  {name}: ✓ Available")
                else:
                    print(f"  {name}: ⚠ Limited")
            except Exception:
                print(f"  {name}: ✗ Unavailable")
