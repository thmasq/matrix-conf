#!/usr/bin/env python3
"""
Matrix Admin Spam Checker Module - Walled Garden Implementation

This module implements a "walled garden" approach where only designated server
administrators can perform certain actions like creating rooms, inviting users,
creating aliases, and publishing rooms to the directory.

Designed to make Matrix behave more like a centralized Discord server.
"""

from typing import Union, Tuple
import logging

from synapse.module_api import ModuleApi, NOT_SPAM, JsonDict
from synapse.module_api.errors import Codes, ConfigError

logger = logging.getLogger(__name__)


class WalledGardenConfig:
    """Configuration for the Walled Garden module."""

    def __init__(self, config: dict):
        self.admin_usernames = set(config.get("admin_usernames", []))

        self.allow_admin_invites_only = config.get("allow_admin_invites_only", True)
        self.allow_admin_room_creation_only = config.get(
            "allow_admin_room_creation_only", True
        )
        self.allow_admin_aliases_only = config.get("allow_admin_aliases_only", True)
        self.allow_admin_publishing_only = config.get(
            "allow_admin_publishing_only", True
        )

        self.invite_rejection_message = config.get(
            "invite_rejection_message",
            "Only server administrators may invite users. Please contact an admin.",
        )
        self.room_creation_rejection_message = config.get(
            "room_creation_rejection_message",
            "Only server administrators may create new rooms/channels. Please contact an admin.",
        )
        self.alias_rejection_message = config.get(
            "alias_rejection_message",
            "Only server administrators may create room aliases.",
        )
        self.publish_rejection_message = config.get(
            "publish_rejection_message",
            "Only server administrators may publish rooms to the directory.",
        )

        if not self.admin_usernames:
            logger.warning(
                "No admin usernames configured. All users will be restricted!"
            )

        logger.info(
            f"Walled Garden configured with {len(self.admin_usernames)} admin users"
        )
        logger.info(
            f"Restrictions - Invites: {self.allow_admin_invites_only}, "
            f"Room creation: {self.allow_admin_room_creation_only}, "
            f"Aliases: {self.allow_admin_aliases_only}, "
            f"Publishing: {self.allow_admin_publishing_only}"
        )


class WalledGarden:
    """
    A spam checker module that implements centralized control over Matrix actions.

    Only designated admin users can:
    - Create rooms/channels
    - Invite other users
    - Create room aliases
    - Publish rooms to the public directory
    """

    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.config = WalledGardenConfig(config)

        self.api.register_spam_checker_callbacks(
            user_may_invite=self.user_may_invite,
            user_may_create_room=self.user_may_create_room,
            user_may_create_room_alias=self.user_may_create_room_alias,
            user_may_publish_room=self.user_may_publish_room,
        )

        logger.info("Walled Garden spam checker module initialized")

    @staticmethod
    def parse_config(config: dict) -> dict:
        """
        Parse and validate the module configuration.

        Args:
            config: Raw configuration dictionary

        Returns:
            Validated configuration dictionary

        Raises:
            ConfigError: If configuration is invalid
        """
        if not isinstance(config, dict):
            raise ConfigError("Configuration must be a dictionary")

        admin_usernames = config.get("admin_usernames", [])
        if not isinstance(admin_usernames, list):
            raise ConfigError("admin_usernames must be a list")

        if not admin_usernames:
            logger.warning(
                "No admin usernames specified - all users will be restricted!"
            )

        for username in admin_usernames:
            if not isinstance(username, str):
                raise ConfigError(
                    f"Admin username must be a string, got: {type(username)}"
                )
            if "@" in username or ":" in username:
                raise ConfigError(
                    f"Admin username should be local part only (no @ or :), got: {username}"
                )

        return config

    def _extract_username(self, user_id: str) -> str:
        """
        Extract the local username from a full Matrix user ID.

        Args:
            user_id: Full Matrix user ID like "@alice:example.com"

        Returns:
            Local username like "alice"
        """
        if user_id.startswith("@"):
            user_id = user_id[1:]

        if ":" in user_id:
            return user_id.split(":", 1)[0]

        return user_id

    def _is_admin(self, user_id: str) -> bool:
        """
        Check if a user is configured as an admin.

        Args:
            user_id: Full Matrix user ID

        Returns:
            True if user is an admin, False otherwise
        """
        username = self._extract_username(user_id)
        is_admin = username in self.config.admin_usernames

        logger.debug(f"Admin check for {user_id} (username: {username}): {is_admin}")
        return is_admin

    async def user_may_invite(
        self, inviter: str, invitee: str, room_id: str
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """
        Check if a user may invite another user to a room.

        Args:
            inviter: Matrix user ID of the person sending the invite
            invitee: Matrix user ID of the person being invited
            room_id: Matrix room ID where the invite is being sent

        Returns:
            NOT_SPAM if allowed, (error_code, message) tuple if blocked
        """
        if not self.config.allow_admin_invites_only:
            return NOT_SPAM

        if self._is_admin(inviter):
            logger.info(f"Admin {inviter} invited {invitee} to {room_id}")
            return NOT_SPAM

        logger.info(
            f"Blocked invite from non-admin {inviter} to {invitee} in {room_id}"
        )
        return (Codes.FORBIDDEN, self.config.invite_rejection_message)

    async def user_may_create_room(
        self, user_id: str, room_config: JsonDict
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """
        Check if a user may create a room.

        Args:
            user_id: Matrix user ID of the person creating the room
            room_config: Room creation configuration from the client

        Returns:
            NOT_SPAM if allowed, (error_code, message) tuple if blocked
        """
        if not self.config.allow_admin_room_creation_only:
            return NOT_SPAM

        if self._is_admin(user_id):
            room_name = room_config.get("name", "unnamed room")
            logger.info(f"Admin {user_id} created room: {room_name}")
            return NOT_SPAM

        logger.info(f"Blocked room creation by non-admin {user_id}")
        return (Codes.FORBIDDEN, self.config.room_creation_rejection_message)

    async def user_may_create_room_alias(
        self, user_id: str, room_alias: str
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """
        Check if a user may create a room alias.

        Args:
            user_id: Matrix user ID of the person creating the alias
            room_alias: The room alias being created

        Returns:
            NOT_SPAM if allowed, (error_code, message) tuple if blocked
        """
        if not self.config.allow_admin_aliases_only:
            return NOT_SPAM

        if self._is_admin(user_id):
            logger.info(f"Admin {user_id} created alias: {room_alias}")
            return NOT_SPAM

        logger.info(f"Blocked alias creation by non-admin {user_id}: {room_alias}")
        return (Codes.FORBIDDEN, self.config.alias_rejection_message)

    async def user_may_publish_room(
        self, user_id: str, room_id: str
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """
        Check if a user may publish a room to the public directory.

        Args:
            user_id: Matrix user ID of the person publishing the room
            room_id: Matrix room ID being published

        Returns:
            NOT_SPAM if allowed, (error_code, message) tuple if blocked
        """
        if not self.config.allow_admin_publishing_only:
            return NOT_SPAM

        if self._is_admin(user_id):
            logger.info(f"Admin {user_id} published room {room_id} to directory")
            return NOT_SPAM

        logger.info(f"Blocked room publishing by non-admin {user_id}: {room_id}")
        return (Codes.FORBIDDEN, self.config.publish_rejection_message)
