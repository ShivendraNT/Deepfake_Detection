"""Unit tests cannot reach the network (conftest guard)."""

from __future__ import annotations

import socket

import pytest


def test_socket_connect_is_blocked() -> None:
    with pytest.raises(RuntimeError, match="Network access is disabled"):
        socket.create_connection(("example.com", 80), timeout=1)
