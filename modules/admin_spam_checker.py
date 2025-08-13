#!/usr/bin/env python3
"""
Matrix Admin Spam Checker Module - Walled Garden Implementation

This module implements a "walled garden" approach where only designated server
administrators can perform certain actions like creating rooms, inviting users,
creating aliases, and publishing rooms to the directory.

Designed to make Matrix behave more like a centralized Discord server.
"""

import time
from typing import Union, Tuple, Dict
import logging
from threading import Lock

from synapse.module_api import ModuleApi, NOT_SPAM, JsonDict
from synapse.module_api.errors import Codes, ConfigError

logger = logging.getLogger(__name__)


class DMTracker:
    """Tracks recently created DM rooms to allow subsequent invites."""

    def __init__(self, ttl_seconds: int = 3):
        self.ttl_seconds = ttl_seconds
        self._dm_rooms: Dict[str, Dict[str, Union[str, float]]] = {}
        self._lock = Lock()

    def add_dm_room(self, room_id: str, creator_user_id: str) -> None:
        """Add a DM room to tracking with TTL."""
        with self._lock:
            self._dm_rooms[room_id] = {
                "creator": creator_user_id,
                "created_at": time.time(),
            }
            logger.debug(f"Added DM room {room_id} created by {creator_user_id}")

    def can_invite_to_dm(self, room_id: str, inviter_user_id: str) -> bool:
        """Check if user can invite to a tracked DM room."""
        with self._lock:
            self._cleanup_expired()

            if room_id not in self._dm_rooms:
                return False

            room_info = self._dm_rooms[room_id]
            return room_info["creator"] == inviter_user_id

    def remove_dm_room(self, room_id: str) -> None:
        """Remove a DM room from tracking (called after successful invite)."""
        with self._lock:
            if room_id in self._dm_rooms:
                creator = self._dm_rooms[room_id]["creator"]
                del self._dm_rooms[room_id]
                logger.debug(
                    f"Removed DM room {room_id} from tracking (creator: {creator})"
                )

    def _cleanup_expired(self) -> None:
        """Remove expired DM room entries."""
        current_time = time.time()
        expired_rooms = [
            room_id
            for room_id, info in self._dm_rooms.items()
            if current_time - info["created_at"] > self.ttl_seconds
        ]

        for room_id in expired_rooms:
            creator = self._dm_rooms[room_id]["creator"]
            del self._dm_rooms[room_id]
            logger.debug(f"Expired DM room {room_id} created by {creator}")

    def get_stats(self) -> Dict[str, int]:
        """Get current tracking statistics."""
        with self._lock:
            self._cleanup_expired()
            return {
                "tracked_dm_rooms": len(self._dm_rooms),
                "ttl_seconds": self.ttl_seconds,
            }


class WalledGarden:
    """
    A spam checker module that implements centralized control over Matrix actions.

    Only designated admin users can:
    - Create rooms/channels (except DMs if enabled)
    - Invite other users (except to their own DMs if enabled)
    - Create room aliases
    - Publish rooms to the public directory

    With DM support enabled, regular users can:
    - Create direct message rooms (with strict validation)
    - Invite one person to their newly created DM (with time limit)
    """

    def __init__(self, config: dict, api: ModuleApi):
        self.api = api
        self.config = self._parse_and_validate_config(config)

        if self.config["allow_dm_creation"]:
            self.dm_tracker = DMTracker(self.config["dm_invite_ttl_seconds"])
            self._recent_dm_creations: Dict[str, float] = {}
            self._creation_lock = Lock()
        else:
            self.dm_tracker = None

        self.api.register_spam_checker_callbacks(
            user_may_invite=self.user_may_invite,
            user_may_create_room=self.user_may_create_room,
            user_may_create_room_alias=self.user_may_create_room_alias,
            user_may_publish_room=self.user_may_publish_room,
        )

        try:
            self.api.register_spam_checker_callbacks(
                check_event_for_spam=self._check_room_creation_event,
            )
        except Exception as e:
            logger.warning(f"Could not register room creation event callback: {e}")

        logger.info("Walled Garden spam checker module initialized")

    def _parse_and_validate_config(self, config: dict) -> dict:
        """Parse and validate the module configuration."""
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

        allow_dm_creation = config.get("allow_dm_creation", False)
        if not isinstance(allow_dm_creation, bool):
            raise ConfigError("allow_dm_creation must be a boolean")

        dm_invite_ttl_seconds = config.get("dm_invite_ttl_seconds", 300)
        if not isinstance(dm_invite_ttl_seconds, int) or dm_invite_ttl_seconds <= 0:
            raise ConfigError("dm_invite_ttl_seconds must be a positive integer")

        processed_config = {
            "admin_usernames": set(admin_usernames),
            "allow_admin_invites_only": config.get("allow_admin_invites_only", True),
            "allow_admin_room_creation_only": config.get(
                "allow_admin_room_creation_only", True
            ),
            "allow_admin_aliases_only": config.get("allow_admin_aliases_only", True),
            "allow_admin_publishing_only": config.get(
                "allow_admin_publishing_only", True
            ),
            "allow_dm_creation": allow_dm_creation,
            "dm_invite_ttl_seconds": dm_invite_ttl_seconds,
            "invite_rejection_message": config.get(
                "invite_rejection_message",
                "Only server administrators may invite users. Please contact an admin.",
            ),
            "room_creation_rejection_message": config.get(
                "room_creation_rejection_message",
                "Only server administrators may create new rooms/channels. Please contact an admin.",
            ),
            "alias_rejection_message": config.get(
                "alias_rejection_message",
                "Only server administrators may create room aliases.",
            ),
            "publish_rejection_message": config.get(
                "publish_rejection_message",
                "Only server administrators may publish rooms to the directory.",
            ),
        }

        logger.info(
            f"Walled Garden configured with {len(processed_config['admin_usernames'])} admin users"
        )
        logger.info(
            f"Restrictions - Invites: {processed_config['allow_admin_invites_only']}, "
            f"Room creation: {processed_config['allow_admin_room_creation_only']}, "
            f"Aliases: {processed_config['allow_admin_aliases_only']}, "
            f"Publishing: {processed_config['allow_admin_publishing_only']}"
        )
        logger.info(
            f"DM Support - Creation: {processed_config['allow_dm_creation']}, "
            f"Invite TTL: {processed_config['dm_invite_ttl_seconds']}s"
        )

        return processed_config

    @staticmethod
    def parse_config(config: dict) -> dict:
        """Static method for Synapse to validate config during startup."""
        return config

    def _extract_username(self, user_id: str) -> str:
        """Extract the local username from a full Matrix user ID."""
        if user_id.startswith("@"):
            user_id = user_id[1:]
        if ":" in user_id:
            return user_id.split(":", 1)[0]
        return user_id

    def _is_admin(self, user_id: str) -> bool:
        """Check if a user is configured as an admin."""
        username = self._extract_username(user_id)
        is_admin = username in self.config["admin_usernames"]
        logger.debug(f"Admin check for {user_id} (username: {username}): {is_admin}")
        return is_admin

    def _is_legitimate_dm_creation(self, room_config: JsonDict) -> bool:
        """
        Determine if a room creation request is for a legitimate DM.

        A legitimate DM must:
        1. Have is_direct=true OR preset="trusted_private_chat"
        2. Have 0 or 1 users in the invite list (not multiple users)
        3. Not have a room name (DMs shouldn't have names)
        4. Not have a topic (DMs shouldn't have topics)
        5. Not have a room alias (DMs shouldn't have aliases)
        6. Be private (DMs shouldn't be public)
        """
        logger.debug(f"Validating DM creation request: {room_config}")

        is_direct = room_config.get("is_direct") is True
        preset = room_config.get("preset")
        has_dm_preset = preset == "trusted_private_chat"

        logger.debug(f"DM indicators: is_direct={is_direct}, preset={preset}")

        if not (is_direct or has_dm_preset):
            logger.debug(
                f"Room creation not identified as DM: is_direct={is_direct}, preset={preset}"
            )
            return False

        invite_list = room_config.get("invite", [])
        if not isinstance(invite_list, list):
            logger.warning(f"Invalid invite list type: {type(invite_list)}")
            return False

        logger.debug(f"Invite list: {invite_list} (length: {len(invite_list)})")

        if len(invite_list) > 1:
            logger.warning(
                f"Fake DM detected: is_direct={is_direct}, preset={preset}, "
                f"but has {len(invite_list)} invites: {invite_list}"
            )
            return False

        room_name = room_config.get("name")
        if room_name and room_name.strip():
            logger.warning(
                f"Fake DM detected: has DM flags but also has room name: '{room_name}'"
            )
            return False

        room_topic = room_config.get("topic")
        if room_topic and room_topic.strip():
            logger.warning(
                f"Fake DM detected: has DM flags but also has room topic: '{room_topic}'"
            )
            return False

        room_alias = room_config.get("room_alias_name")
        if room_alias and room_alias.strip():
            logger.warning(
                f"Fake DM detected: has DM flags but also has room alias: '{room_alias}'"
            )
            return False

        visibility = room_config.get("visibility", "private")
        if visibility != "private":
            logger.warning(
                f"Fake DM detected: has DM flags but visibility is '{visibility}' (should be private)"
            )
            return False

        logger.debug(
            f"Legitimate DM creation detected: is_direct={is_direct}, "
            f"preset={preset}, invites={len(invite_list)}"
        )
        return True

    async def _check_room_creation_event(self, event: JsonDict) -> Union[NOT_SPAM, str]:
        """Check room creation events to track DM rooms."""
        if event.get("type") != "m.room.create":
            return NOT_SPAM

        room_id = event.get("room_id")
        creator = event.get("sender")

        if not room_id or not creator or not self.dm_tracker:
            return NOT_SPAM

        # Check if this user recently requested DM creation
        # Note: This might already be handled in user_may_invite for immediate invites
        with self._creation_lock:
            if creator in self._recent_dm_creations:
                # Only add to tracking if not already tracked
                # (in case user_may_invite already handled this)
                if not self.dm_tracker.can_invite_to_dm(room_id, creator):
                    self.dm_tracker.add_dm_room(room_id, creator)
                    logger.info(f"Tracked new DM room {room_id} for user {creator}")

                # Clean up the recent creation tracking
                del self._recent_dm_creations[creator]

        return NOT_SPAM

    async def user_may_invite(
        self, inviter: str, invitee: str, room_id: str
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """Check if a user may invite another user to a room."""
        logger.debug(f"Checking invite: {inviter} -> {invitee} in {room_id}")

        if not self.config["allow_admin_invites_only"]:
            logger.debug("Admin-only invites disabled, allowing all invites")
            return NOT_SPAM

        if self._is_admin(inviter):
            logger.info(f"Admin {inviter} invited {invitee} to {room_id}")
            return NOT_SPAM

        # Check if this is an invite to a recently created DM by the same user
        if (
            self.config["allow_dm_creation"]
            and self.dm_tracker
            and self.dm_tracker.can_invite_to_dm(room_id, inviter)
        ):
            logger.info(
                f"Allowing DM invite from {inviter} to {invitee} in {room_id} (room already tracked)"
            )

            # Remove the room from tracking after the invite
            self.dm_tracker.remove_dm_room(room_id)
            return NOT_SPAM

        # Check if this user just created a DM (for immediate invite during room creation)
        if self.config["allow_dm_creation"] and self.dm_tracker:
            logger.debug(f"Checking recent DM creations for {inviter}")
            with self._creation_lock:
                if inviter in self._recent_dm_creations:
                    # This is likely the initial invite during DM creation
                    # Add the room to tracking and allow this invite
                    logger.info(
                        f"Allowing initial DM invite from {inviter} to {invitee} in {room_id} (during room creation)"
                    )

                    # Track this room for any future invites
                    self.dm_tracker.add_dm_room(room_id, inviter)

                    # Clean up the recent creation tracking
                    del self._recent_dm_creations[inviter]

                    return NOT_SPAM
                else:
                    logger.debug(
                        f"User {inviter} not found in recent DM creations: {list(self._recent_dm_creations.keys())}"
                    )

        logger.info(
            f"Blocked invite from non-admin {inviter} to {invitee} in {room_id}"
        )
        return (Codes.FORBIDDEN, self.config["invite_rejection_message"])

    async def user_may_create_room(
        self, user_id: str, room_config: JsonDict
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """Check if a user may create a room."""
        logger.debug(f"Checking room creation by {user_id}: {room_config}")

        if not self.config["allow_admin_room_creation_only"]:
            logger.debug(
                "Admin-only room creation disabled, allowing all room creation"
            )
            return NOT_SPAM

        # Always allow admin room creation
        if self._is_admin(user_id):
            room_name = room_config.get("name", "unnamed room")
            logger.info(f"Admin {user_id} created room: {room_name}")
            return NOT_SPAM

        # Check if DM creation is allowed and this is a legitimate DM
        if self.config["allow_dm_creation"] and self._is_legitimate_dm_creation(
            room_config
        ):
            logger.info(f"Allowing legitimate DM creation by {user_id}")

            # Track this user's DM creation request for the room creation event
            if self.dm_tracker:
                with self._creation_lock:
                    self._recent_dm_creations[user_id] = time.time()
                    logger.debug(
                        f"Added {user_id} to recent DM creations. Current list: {list(self._recent_dm_creations.keys())}"
                    )

            return NOT_SPAM

        logger.info(f"Blocked room creation by non-admin {user_id}")
        return (Codes.FORBIDDEN, self.config["room_creation_rejection_message"])

    async def user_may_create_room_alias(
        self, user_id: str, room_alias: str
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """Check if a user may create a room alias."""
        if not self.config["allow_admin_aliases_only"]:
            return NOT_SPAM

        if self._is_admin(user_id):
            logger.info(f"Admin {user_id} created alias: {room_alias}")
            return NOT_SPAM

        logger.info(f"Blocked alias creation by non-admin {user_id}: {room_alias}")
        return (Codes.FORBIDDEN, self.config["alias_rejection_message"])

    async def user_may_publish_room(
        self, user_id: str, room_id: str
    ) -> Union[NOT_SPAM, Tuple[Codes, str]]:
        """Check if a user may publish a room to the public directory."""
        if not self.config["allow_admin_publishing_only"]:
            return NOT_SPAM

        if self._is_admin(user_id):
            logger.info(f"Admin {user_id} published room {room_id} to directory")
            return NOT_SPAM

        logger.info(f"Blocked room publishing by non-admin {user_id}: {room_id}")
        return (Codes.FORBIDDEN, self.config["publish_rejection_message"])
