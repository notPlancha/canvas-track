"""Unit tests for MoodleClient."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from canvas_track.moodle_client import MoodleAPIError, MoodleClient


@pytest.mark.anyio
async def test_moodle_client_get_site_info() -> None:
    client = MoodleClient("https://moodle.example.edu", "mock_token")

    mock_resp = httpx.Response(
        status_code=200,
        json={
            "sitename": "Test Moodle",
            "username": "student1",
            "firstname": "Test",
            "lastname": "Student",
            "fullname": "Test Student",
            "userid": 42,
        },
        request=httpx.Request("POST", client.api_url),
    )

    with patch.object(client._get_client(), "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        info = await client.get_site_info()
        assert info["userid"] == 42
        assert info["fullname"] == "Test Student"
        assert info["sitename"] == "Test Moodle"

    await client.aclose()


@pytest.mark.anyio
async def test_moodle_client_error_handling() -> None:
    client = MoodleClient("https://moodle.example.edu", "invalid_token")

    mock_resp = httpx.Response(
        status_code=200,
        json={
            "exception": "core\\exception\\moodle_exception",
            "errorcode": "invalidtoken",
            "message": "Invalid token",
        },
        request=httpx.Request("POST", client.api_url),
    )

    with patch.object(client._get_client(), "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(MoodleAPIError) as exc_info:
            await client.get_site_info()
        assert "invalidtoken" in str(exc_info.value)

    await client.aclose()


@pytest.mark.anyio
async def test_moodle_client_download_file(tmp_path: Path) -> None:
    client = MoodleClient("https://moodle.example.edu", "test_token")
    dest = tmp_path / "test_file.txt"

    with patch.object(client._get_client(), "stream") as mock_stream:
        # Mock stream context manager
        mock_cm = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200

        async def fake_aiter(*args, **kwargs):
            yield b"Hello Moodle File Content"

        mock_response.aiter_bytes = fake_aiter
        mock_cm.__aenter__.return_value = mock_response
        mock_cm.__aexit__.return_value = None
        mock_stream.return_value = mock_cm

        success = await client.download_file(
            "https://moodle.example.edu/pluginfile.php/123/file.txt", dest
        )
        assert success
        assert dest.exists()
        assert dest.read_bytes() == b"Hello Moodle File Content"

    await client.aclose()
