"""传输层认证模块单测（SimpleTokenVerifier）。"""

from __future__ import annotations

import pytest

from src.core.auth import AccessToken, SimpleTokenVerifier


@pytest.mark.asyncio
async def test_verify_valid_token() -> None:
    verifier = SimpleTokenVerifier(valid_tokens={"secret-1"})
    result = await verifier.verify_token("secret-1")

    assert isinstance(result, AccessToken)
    assert result.token == "secret-1"
    assert result.client_id == "qiuchi"


@pytest.mark.asyncio
async def test_verify_invalid_token_returns_none() -> None:
    verifier = SimpleTokenVerifier(valid_tokens={"secret-1"})
    assert await verifier.verify_token("wrong") is None


@pytest.mark.asyncio
async def test_verify_empty_tokens_rejects_all() -> None:
    verifier = SimpleTokenVerifier()
    assert await verifier.verify_token("anything") is None


@pytest.mark.asyncio
async def test_add_and_remove_token() -> None:
    verifier = SimpleTokenVerifier()
    verifier.add_token("new-token")
    assert await verifier.verify_token("new-token") is not None

    assert verifier.remove_token("new-token") is True
    assert await verifier.verify_token("new-token") is None

    assert verifier.remove_token("non-existent") is False


def test_custom_client_id() -> None:
    verifier = SimpleTokenVerifier(valid_tokens={"t"}, client_id="custom-app")
    assert verifier.client_id == "custom-app"
