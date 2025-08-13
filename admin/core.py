"""Core Matrix API client and configuration management."""

from __future__ import annotations

import getpass
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class MatrixClient:
    """Core Matrix API client for server communication."""

    def __init__(
        self,
        base_url: str | None = None,
        admin_token: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.admin_token = admin_token or ""

    def make_request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
    ) -> dict | None:
        """Make HTTP request to Matrix server."""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json",
        }

        try:
            if data:
                data_bytes = json.dumps(data).encode("utf-8")
                request = urllib.request.Request(
                    url,
                    data=data_bytes,
                    headers=headers,
                    method=method,
                )
            else:
                request = urllib.request.Request(url, headers=headers, method=method)

            with urllib.request.urlopen(request) as response:
                return json.loads(response.read().decode("utf-8"))

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode("utf-8")
            try:
                error_json = json.loads(error_msg)
                msg = f"HTTP {e.code}: {error_json.get('error', error_msg)}"
                raise Exception(msg)
            except json.JSONDecodeError:
                msg = f"HTTP {e.code}: {error_msg}"
                raise Exception(msg)
        except Exception as e:
            msg = f"Request failed: {e}"
            raise Exception(msg)

    def test_connection(self) -> bool:
        """Test the Matrix server connection and admin token."""
        try:
            response = self.make_request("GET", "/_matrix/client/r0/account/whoami")
            if response and "user_id" in response:
                print(f"Connected as: {response['user_id']}")
                return True
        except Exception as e:
            print(f"Connection failed: {e}")
        return False

    def get_room_id_from_alias(self, room_alias: str) -> str | None:
        """Convert room alias to room ID."""
        try:
            encoded_alias = urllib.parse.quote(room_alias, safe="")
            response = self.make_request(
                "GET",
                f"/_matrix/client/r0/directory/room/{encoded_alias}",
            )
            return response.get("room_id") if response else None
        except Exception:
            return None

    def resolve_room_identifier(self, identifier: str) -> tuple[str, str]:
        """Resolve room alias or ID to room ID and display name."""
        if identifier.startswith("#"):
            room_id = self.get_room_id_from_alias(identifier)
            if not room_id:
                msg = f"Could not find room with alias: {identifier}"
                raise Exception(msg)
            return room_id, identifier
        return identifier, identifier


class ConfigManager:
    """Manage application configuration and setup."""

    @staticmethod
    def load_config() -> dict[str, str]:
        """Load configuration from .env file or environment variables."""
        config = {}

        # Try loading from .env file
        if os.path.exists(".env"):
            with open(".env") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        config[key.lower()] = value

        # Override with environment variables
        config["homeserver_url"] = os.getenv(
            "HOMESERVER_URL",
            config.get("homeserver_url", ""),
        )
        config["admin_token"] = os.getenv("ADMIN_TOKEN", config.get("admin_token", ""))

        return config

    @staticmethod
    def setup_config_interactive(client: MatrixClient) -> bool:
        """Interactive configuration setup."""
        from .ui import ScreenManager

        screen_manager = ScreenManager()
        screen_manager.show_header("Matrix Admin Configuration Setup")

        if not client.base_url:
            client.base_url = input(
                "Enter Matrix homeserver URL (e.g., https://matrix.example.com): ",
            ).strip()

        if not client.admin_token:
            print("\nTo get an admin token:")
            print("1. Create an admin user if you haven't already")
            print("2. Use this curl command to get a token:")
            print(f'   curl -X POST "{client.base_url}/_matrix/client/r0/login" \\')
            print('   -H "Content-Type: application/json" \\')
            print(
                '   -d \'{"type": "m.login.password", "user": "admin", "password": "your_password"}\'',
            )
            print("\n3. Copy the access_token from the response")

            client.admin_token = getpass.getpass("Enter admin access token: ").strip()

        # Test the configuration
        if client.test_connection():
            print("Configuration successful!")
            screen_manager.pause_for_input()
            return True
        print("Configuration failed. Please check your settings.")
        screen_manager.pause_for_input()
        return False
