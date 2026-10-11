#!/usr/bin/env python3
"""传输配置单测（TransportConfig / get_transport_config）。"""

from __future__ import annotations

import pytest

from src.constants import TransportType
from src.transport import TransportConfig, get_transport_config


class TestTransportConfig:
    def test_defaults(self) -> None:
        cfg = TransportConfig()
        assert cfg.transport == TransportType.STREAMABLE_HTTP
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8888

    def test_from_string(self) -> None:
        cases = [
            ("stdio", TransportType.STDIO),
            ("sse", TransportType.SSE),
            ("streamable-http", TransportType.STREAMABLE_HTTP),
        ]
        for transport_str, expected in cases:
            cfg = TransportConfig.from_string(transport_str, "127.0.0.1", 9000)
            assert cfg.transport == expected
            assert cfg.host == "127.0.0.1"
            assert cfg.port == 9000

    def test_from_string_invalid(self) -> None:
        with pytest.raises(ValueError):
            TransportConfig.from_string("ftp")

    def test_override_constructor(self) -> None:
        cfg = TransportConfig(transport=TransportType.STDIO, host="127.0.0.1", port=1)
        assert (cfg.transport, cfg.host, cfg.port) == (TransportType.STDIO, "127.0.0.1", 1)


class TestGetTransportConfig:
    def test_from_string(self) -> None:
        cfg = get_transport_config("sse", "127.0.0.1", 9001)
        assert cfg.transport == TransportType.SSE
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9001

    def test_from_enum(self) -> None:
        cfg = get_transport_config(TransportType.STDIO)
        assert cfg.transport == TransportType.STDIO
        assert cfg.port == 8888  # 默认端口

    def test_defaults(self) -> None:
        cfg = get_transport_config("stdio")
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8888
