import asyncio
from unittest.mock import AsyncMock

def test_parse_aot_payload_extracts_token_and_device_uuid():
    from plugins.platforms.iris.kakao_reaction import parse_aot_payload
    body = {'success': True, 'aot': {'access_token': 'token-abc', 'd_id': 'device-xyz'}}
    token, device_uuid = parse_aot_payload(body)
    assert token == 'token-abc'
    assert device_uuid == 'device-xyz'

def test_build_reaction_body_includes_link_id_for_open_chat():
    from plugins.platforms.iris.kakao_reaction import build_reaction_body
    body = build_reaction_body('12345', reaction_type=3, link_id=467826254, req_id=999)
    assert body == {'logId': 12345, 'reqId': 999, 'type': 3, 'linkId': 467826254}

def test_build_reaction_body_omits_link_id_for_regular_chat():
    from plugins.platforms.iris.kakao_reaction import build_reaction_body
    body = build_reaction_body('12345', reaction_type=3, req_id=999)
    assert body == {'logId': 12345, 'reqId': 999, 'type': 3}
    assert 'linkId' not in body

def test_build_reaction_authorization_format():
    from plugins.platforms.iris.kakao_reaction import build_reaction_authorization
    assert build_reaction_authorization('tok', 'did') == 'tok-did'

def test_send_kakao_reaction_success():
    from plugins.platforms.iris.kakao_reaction import send_kakao_reaction

    class FakeResponse:
        status_code = 200

        def json(self):
            return {'result': True}

        @property
        def content(self):
            return b'{"result":true}'

    class FakeClient:

        async def post(self, url, headers=None, json=None):
            assert 'bubble/reactions' in url
            assert headers['Authorization'] == 'tok-did'
            assert json['type'] == 3
            return FakeResponse()
    ok = asyncio.run(send_kakao_reaction('18486847620593103', '3870805187836121090', 'tok', 'did', link_id=467826254, client=FakeClient()))
    assert ok is True

class DummyConfig:

    def __init__(self, extra=None):
        self.extra = extra or {}

def test_handle_inbound_schedules_check_reaction(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageEvent, MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000, 'allowed_chat_ids': ['room-1']}))
    scheduled = []
    adapter._schedule_check_reaction = lambda chat_id, log_id: scheduled.append((chat_id, log_id))
    adapter.handle_message = AsyncMock()
    event = MessageEvent(text='hello', message_type=MessageType.TEXT, source=adapter.build_source(chat_id='room-1', user_id='999', user_name='user'), message_id='123456789')
    consumed = asyncio.run(adapter._handle_inbound_event(event))
    assert consumed is True
    assert scheduled == [('room-1', '123456789')]
    adapter.handle_message.assert_awaited_once()

def test_get_link_id_queries_chat_rooms(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000}))

    async def fake_query(query, bind=None):
        assert 'chat_rooms' in query
        return [{'link_id': '467826254'}]
    adapter._iris_query = fake_query
    link_id = asyncio.run(adapter._get_link_id('18486847620593103'))
    assert link_id == 467826254
    assert adapter._link_id_cache['18486847620593103'] == 467826254
