import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from service import app
from service.service import limit_agent_concurrency


@pytest.mark.asyncio
async def test_concurrency_slot_is_released() -> None:
    semaphore = asyncio.Semaphore(1)

    with patch("service.service._agent_run_semaphore", semaphore):
        dependency = limit_agent_concurrency()
        await anext(dependency)

        assert semaphore.locked()

        await dependency.aclose()

    assert not semaphore.locked()


@pytest.mark.asyncio
async def test_concurrency_queue_timeout_returns_429() -> None:
    semaphore = asyncio.Semaphore(1)
    await semaphore.acquire()

    with (
        patch("service.service._agent_run_semaphore", semaphore),
        patch("service.service._agent_queue_timeout_seconds", 0.01),
    ):
        dependency = limit_agent_concurrency()

        with pytest.raises(HTTPException) as exc_info:
            await anext(dependency)

    semaphore.release()

    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/invoke", "/chatbot/invoke", "/stream", "/chatbot/stream"])
async def test_busy_routes_reject_before_response_starts(path: str, mock_agent) -> None:
    semaphore = asyncio.Semaphore(1)
    await semaphore.acquire()
    with (
        patch("service.service._agent_run_semaphore", semaphore),
        patch("service.service._agent_queue_timeout_seconds", 0.01),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(path, json={"message": "test"})
    semaphore.release()

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "1"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    mock_agent.ainvoke.assert_not_called()
    mock_agent.astream.assert_not_called()


@pytest.mark.asyncio
async def test_stream_holds_slot_until_body_complete(mock_agent) -> None:
    semaphore = asyncio.Semaphore(1)
    started = asyncio.Event()
    finish_stream = asyncio.Event()

    async def paused_stream(*args):
        started.set()
        yield 'data: {"type": "token", "content": "hello"}\n\n'
        await finish_stream.wait()
        yield "data: [DONE]\n\n"

    with (
        patch("service.service._agent_run_semaphore", semaphore),
        patch("service.service._agent_queue_timeout_seconds", 0.01),
        patch("service.service.message_generator", paused_stream),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first_request = asyncio.create_task(
                client.post("/chatbot/stream", json={"message": "stream"})
            )
            try:
                await asyncio.wait_for(started.wait(), timeout=2)
                busy_response = await client.post("/chatbot/invoke", json={"message": "busy"})
                assert busy_response.status_code == 429
                assert semaphore.locked()
            finally:
                finish_stream.set()
                first_response = await asyncio.wait_for(first_request, timeout=2)

            assert first_response.status_code == 200
            assert "[DONE]" in first_response.text
            assert not semaphore.locked()
            next_response = await client.post("/chatbot/invoke", json={"message": "next"})
            assert next_response.status_code == 200
