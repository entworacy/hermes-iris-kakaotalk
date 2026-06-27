import asyncio
from unittest.mock import AsyncMock
from plugins.platforms.iris.iris_config import fetch_iris_config, parse_iris_config

def test_parse_iris_config_extracts_bot_id_and_name():
    bot_id, bot_name = parse_iris_config({'bot_id': 443332129, 'bot_name': 'MyBot', 'bot_http_port': 3000})
    assert bot_id == '443332129'
    assert bot_name == 'MyBot'

def test_parse_iris_config_handles_missing_fields():
    assert parse_iris_config({}) == (None, None)
    assert parse_iris_config(None) == (None, None)

def test_fetch_iris_config_success():

    class FakeResponse:

        def raise_for_status(self):
            return None

        def json(self):
            return {'bot_id': 12345, 'bot_name': 'Iris'}
    client = AsyncMock()
    client.get = AsyncMock(return_value=FakeResponse())
    bot_id, bot_name = asyncio.run(fetch_iris_config('http://127.0.0.1:3000', client=client))
    assert bot_id == '12345'
    assert bot_name == 'Iris'
    client.get.assert_awaited_once_with('http://127.0.0.1:3000/config')

def test_fetch_iris_config_failure_returns_none():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=OSError('connection refused'))
    bot_id, bot_name = asyncio.run(fetch_iris_config('http://127.0.0.1:3000', client=client))
    assert bot_id is None
    assert bot_name is None
