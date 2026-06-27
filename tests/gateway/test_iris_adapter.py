import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

def test_iris_adapter_module_imports_and_has_register(monkeypatch):
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    from plugins.platforms.iris.adapter import register, check_requirements
    assert callable(register)
    assert callable(check_requirements)

class DummyConfig:

    def __init__(self, extra=None):
        self.extra = extra or {}

def test_check_requirements_and_validate_config(monkeypatch):
    from plugins.platforms.iris.adapter import check_requirements, validate_config
    monkeypatch.delenv('IRIS_HOST', raising=False)
    monkeypatch.delenv('IRIS_PORT', raising=False)
    monkeypatch.delenv('IRIS_BASE_URL', raising=False)
    assert check_requirements() is False
    assert validate_config(DummyConfig()) is False
    monkeypatch.setenv('IRIS_HOST', '192.168.1.10')
    monkeypatch.setenv('IRIS_PORT', '3000')
    assert check_requirements() is True
    assert validate_config(DummyConfig()) is True
    monkeypatch.delenv('IRIS_HOST', raising=False)
    monkeypatch.delenv('IRIS_PORT', raising=False)
    monkeypatch.setenv('IRIS_BASE_URL', 'http://example:1234')
    assert check_requirements() is True
    assert validate_config(DummyConfig()) is True
    monkeypatch.delenv('IRIS_BASE_URL', raising=False)
    cfg = DummyConfig({'host': '10.0.0.1', 'port': '4000'})
    assert validate_config(cfg) is True
    cfg2 = DummyConfig({'base_url': 'http://foo:9999'})
    assert validate_config(cfg2) is True

def test_iris_adapter_init_various_configs(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    for k in ('IRIS_HOST', 'IRIS_PORT', 'IRIS_BASE_URL', 'IRIS_ALLOWED_CHAT_IDS'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    a1 = IrisAdapter(DummyConfig())
    assert a1._host == '127.0.0.1'
    assert a1._port == 3000
    assert a1._base_url == 'http://127.0.0.1:3000'
    assert a1._ws_url == 'ws://127.0.0.1:3000/ws'
    assert a1._allowed_chat_ids == set()
    monkeypatch.delenv('IRIS_HOST', raising=False)
    monkeypatch.delenv('IRIS_PORT', raising=False)
    a2 = IrisAdapter(DummyConfig({'base_url': 'https://myiris:8443'}))
    assert a2._base_url == 'https://myiris:8443'
    assert a2._ws_url == 'wss://myiris:8443/ws'
    monkeypatch.setenv('IRIS_ALLOWED_CHAT_IDS', '123, 456 ,789')
    a3 = IrisAdapter(DummyConfig())
    assert a3._allowed_chat_ids == {'123', '456', '789'}
    monkeypatch.delenv('IRIS_ALLOWED_CHAT_IDS', raising=False)
    a4 = IrisAdapter(DummyConfig({'allowed_chat_ids': [123, '  456 ', 789]}))
    assert a4._allowed_chat_ids == {'123', '456', '789'}
    for k in ('IRIS_HOST', 'IRIS_PORT', 'IRIS_BASE_URL'):
        monkeypatch.delenv(k, raising=False)
    a5 = IrisAdapter(DummyConfig())
    assert 'http://:' not in (a5._base_url or '')
    assert 'ws://:' not in (a5._ws_url or '')
    assert isinstance(a5._port, int)

def test_iris_adapter_init_robust_port(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    for k in ('IRIS_HOST', 'IRIS_PORT', 'IRIS_BASE_URL', 'IRIS_ALLOWED_CHAT_IDS'):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv('IRIS_PORT', 'notanumber')
    a = IrisAdapter(DummyConfig({'host': 'h'}))
    assert a._port in (0, 3000) or isinstance(a._port, int)
    monkeypatch.setenv('IRIS_PORT', '')
    a2 = IrisAdapter(DummyConfig({'host': 'h', 'port': 'bad'}))
    assert isinstance(a2._port, int)

def test_register_smoke(monkeypatch):
    from plugins.platforms.iris.adapter import register
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    ctx = MagicMock()
    register(ctx)
    ctx.register_platform.assert_called_once()
    call_kwargs = ctx.register_platform.call_args.kwargs
    assert call_kwargs['name'] == 'iris'
    assert call_kwargs['label'] == 'Iris (KakaoTalk)'
    assert 'adapter_factory' in call_kwargs
    assert 'check_fn' in call_kwargs
    assert 'validate_config' in call_kwargs
    assert call_kwargs.get('emoji') == '💬'
    assert 'platform_hint' in call_kwargs
    assert 'pii_safe' in call_kwargs
    assert call_kwargs.get('is_connected') is not None
    assert call_kwargs.get('standalone_sender_fn') is not None
    assert call_kwargs.get('setup_fn') is not None

def test_resolve_iris_channel_prompt_prefers_chat_id_then_default(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'channel_prompts': {'room-a': '방 A 전용', '_default': '기본 비서 톤'}}))
    assert adapter._resolve_iris_channel_prompt('room-a') == '방 A 전용'
    assert adapter._resolve_iris_channel_prompt('room-b') == '기본 비서 톤'
    assert adapter._resolve_iris_channel_prompt('') is None

def test_build_message_event_sets_channel_prompt(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'channel_prompts': {'_default': '개인 비서 모드'}}))
    payload = {'msg': 'ㅎㅇ', 'room': '테스트방', 'sender': '홍길동', 'json': {'chat_id': '123456789012345', 'user_id': '999', 'id': 'msg-1', 'message': 'ㅎㅇ', 'type': 1}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event is not None
    assert event.channel_prompt == '개인 비서 모드'

def test_payload_to_message_event_text(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    payload = {'msg': '안녕하세요', 'room': '테스트방', 'sender': '홍길동', 'json': {'chat_id': '123456789012345', 'user_id': '999', 'id': 'msg-1', 'message': '안녕하세요', 'type': 1}}
    event = adapter._payload_to_message_event(payload)
    assert event is not None
    assert event.text == '안녕하세요'
    assert event.message_type == MessageType.TEXT
    assert event.source.chat_id == '123456789012345'
    assert event.source.user_name == '홍길동'
    assert event.source.chat_name == '테스트방'

def test_is_reply_message_and_extract_src_log_id():
    from plugins.platforms.iris.adapter import extract_src_log_id, is_reply_message
    assert is_reply_message(1, None) is False
    assert is_reply_message(26, None) is True
    assert is_reply_message(26 + 16384, None) is True
    assert is_reply_message(1, '{"src_logId": "999", "src_isThread": true}') is True
    assert extract_src_log_id('{"src_logId": 12345}') == '12345'
    assert extract_src_log_id('{}') is None

def test_chat_log_row_to_reply_context_text():
    from plugins.platforms.iris.adapter import chat_log_row_to_reply_context
    ctx = chat_log_row_to_reply_context({'id': '100', 'message': '원본 메시지', 'type': 1, 'attachment': '{}'})
    assert ctx['reply_to_message_id'] == '100'
    assert ctx['reply_to_text'] == '원본 메시지'
    assert ctx['quoted_media_urls'] == []

def test_chat_log_row_to_reply_context_image():
    from plugins.platforms.iris.adapter import chat_log_row_to_reply_context
    ctx = chat_log_row_to_reply_context({'id': '200', 'message': '', 'type': 27, 'attachment': '{"imageUrls": ["https://example.com/q.jpg"]}'})
    assert ctx['reply_to_text'] is None
    assert ctx['quoted_media_urls'] == ['https://example.com/q.jpg']

def test_attach_reply_context_queries_source(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageEvent, MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    queried = []

    async def fake_query(query, bind=None):
        queried.append((query, bind))
        return [{'id': '555', 'message': 'quoted hello', 'type': 1, 'attachment': '{}'}]
    adapter._iris_query = fake_query
    event = MessageEvent(text='답장입니다', message_type=MessageType.TEXT, source=adapter.build_source(chat_id='room-1', user_name='u'), message_id='900')
    json_row = {'id': '900', 'type': 26, 'attachment': '{"src_logId": "555", "src_isThread": true}'}
    asyncio.run(adapter._attach_reply_context(event, json_row))
    assert queried == [('select * from chat_logs where id = ?', ['555'])]
    assert event.reply_to_message_id == '555'
    assert event.reply_to_text == 'quoted hello'

def test_build_message_event_reply_caches_quoted_image(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())

    async def fake_query(query, bind=None):
        return [{'id': '777', 'message': '', 'type': 27, 'attachment': '{"imageUrls": ["https://example.com/orig.jpg"]}'}]

    async def fake_cache(url, display_name='image', kind='image', content_type='application/octet-stream'):
        return {'path': '/tmp/cached/orig.jpg', 'kind': 'image', 'display_name': display_name, 'media_type': 'image/jpeg'}
    adapter._iris_query = fake_query
    monkeypatch.setattr(iris_adapter, 'cache_inbound_media_url', fake_cache)
    payload = {'msg': '이거 분석해줘', 'room': '분석방', 'sender': 'user', 'json': {'chat_id': '111', 'user_id': '222', 'id': '901', 'message': '이거 분석해줘', 'type': 26, 'attachment': '{"src_logId": "777"}'}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event.reply_to_message_id == '777'
    assert event.reply_to_text is None
    assert event.media_urls == ['/tmp/cached/orig.jpg']
    assert event.media_types == ['image/jpeg']
    assert '[Replied-to image' in event.text
    assert '/tmp/cached/orig.jpg' in event.text

def test_payload_to_message_event_image(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    payload = {'msg': '', 'room': '사진방', 'sender': '김철수', 'json': {'chat_id': '111', 'user_id': '222', 'id': 'img-1', 'type': 27, 'attachment': '{"imageUrls": ["https://example.com/a.jpg"]}'}}
    event = adapter._payload_to_message_event(payload)
    assert event is not None
    assert event.message_type in (MessageType.IMAGE, MessageType.PHOTO)
    assert len(event.media_urls) == 1
    assert event.media_urls[0] == 'https://example.com/a.jpg'

def test_is_cr_command():
    from plugins.platforms.iris.adapter import is_cr_command
    assert is_cr_command('!cr') is True
    assert is_cr_command('  !CR  ') is True
    assert is_cr_command('!cr hello') is False
    assert is_cr_command('hello') is False

def test_is_adcr_command():
    from plugins.platforms.iris.adapter import is_adcr_command
    assert is_adcr_command('!adcr') is True
    assert is_adcr_command('  !ADCR  ') is True
    assert is_adcr_command('!adcr extra') is False

def test_ensure_bot_id_fetches_from_config_when_missing(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    config = DummyConfig({'host': '127.0.0.1', 'port': 3000})
    adapter = IrisAdapter(config)
    assert adapter._bot_id is None

    async def fake_fetch(base_url):
        assert base_url == 'http://127.0.0.1:3000'
        return ('443332129', 'IrisBot')
    monkeypatch.setattr(iris_adapter, 'fetch_iris_config', fake_fetch)
    asyncio.run(adapter._ensure_bot_id())
    assert adapter._bot_id == '443332129'
    assert config.extra['bot_id'] == '443332129'
    assert 'IrisBot' in adapter._bot_names

def test_ensure_bot_id_skips_when_already_configured(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000, 'bot_id': '999'}))

    async def fake_fetch(base_url):
        raise AssertionError('fetch should not be called when bot_id is set')
    monkeypatch.setattr(iris_adapter, 'fetch_iris_config', fake_fetch)
    asyncio.run(adapter._ensure_bot_id())
    assert adapter._bot_id == '999'

def test_is_self_message_filters_bot_echo():
    from plugins.platforms.iris.adapter import is_self_message
    assert is_self_message('443332129', 'Iris', bot_id='443332129', bot_names={'Iris'}) is True
    assert is_self_message('999', '홍길동', bot_id='443332129', bot_names={'Iris'}) is False
    assert is_self_message(None, 'Iris', bot_id=None, bot_names={'Iris'}) is True

def test_handle_inbound_ignores_self_message(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageEvent, MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000, 'bot_id': '443332129', 'allowed_chat_ids': ['room-1']}))
    adapter.handle_message = MagicMock()
    payload = {'json': {'chat_id': 'room-1', 'user_id': '443332129', 'message': '네.', 'type': 1, 'v': '{"enc": 30, "origin": "WRITE"}'}}
    event = MessageEvent(text='네.', message_type=MessageType.TEXT, source=adapter.build_source(chat_id='room-1', user_id='443332129', user_name='Iris'), raw_message=payload)
    consumed = asyncio.run(adapter._handle_inbound_event(event, payload))
    assert consumed is False
    adapter.handle_message.assert_not_called()

def test_handle_inbound_does_not_ignore_msg_origin_even_with_bot_user_id(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageEvent, MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000, 'bot_id': '443332129', 'allowed_chat_ids': ['room-1']}))
    adapter.handle_message = AsyncMock()
    payload = {'json': {'chat_id': 'room-1', 'user_id': '443332129', 'message': '안녕', 'type': 1, 'v': '{"enc": 31, "origin": "MSG"}'}}
    event = MessageEvent(text='안녕', message_type=MessageType.TEXT, source=adapter.build_source(chat_id='room-1', user_id='443332129', user_name='Iris'), raw_message=payload)
    consumed = asyncio.run(adapter._handle_inbound_event(event, payload))
    assert consumed is True
    adapter.handle_message.assert_awaited_once()

def test_register_allowed_chat_id_persists(tmp_path):
    from plugins.platforms.iris.adapter import register_allowed_chat_id
    import yaml
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('gateway:\n  platforms:\n    iris:\n      extra: {}\n')
    ok, msg = register_allowed_chat_id('111222333', current_ids=set(), config_path=config_path)
    assert ok is True
    assert '등록 완료' in msg
    assert '111222333' in msg
    saved = yaml.safe_load(config_path.read_text())
    assert saved['gateway']['platforms']['iris']['extra']['allowed_chat_ids'] == ['111222333']

def test_register_allowed_chat_id_merges_existing(tmp_path):
    from plugins.platforms.iris.adapter import register_allowed_chat_id
    import yaml
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('gateway:\n  platforms:\n    iris:\n      extra:\n        allowed_chat_ids:\n          - existing\n')
    ok, msg = register_allowed_chat_id('new-room', current_ids={'existing'}, config_path=config_path)
    assert ok is True
    saved = yaml.safe_load(config_path.read_text())
    assert saved['gateway']['platforms']['iris']['extra']['allowed_chat_ids'] == ['existing', 'new-room']

def test_register_allowed_chat_id_already_registered():
    from plugins.platforms.iris.adapter import register_allowed_chat_id
    ok, msg = register_allowed_chat_id('room-a', current_ids={'room-a'}, config_path=None)
    assert ok is True
    assert '이미 등록' in msg

def test_is_allowed_chat_requires_registration(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    empty = IrisAdapter(DummyConfig())
    assert empty._is_allowed_chat('any-room') is False
    scoped = IrisAdapter(DummyConfig({'allowed_chat_ids': ['room-a', 'room-b']}))
    assert scoped._is_allowed_chat('room-a') is True
    assert scoped._is_allowed_chat('room-c') is False

def test_handle_inbound_event_allowed_room(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'allowed_chat_ids': ['allowed-only']}))
    emitted = []

    async def capture_message(event):
        emitted.append(event)
    adapter.handle_message = capture_message
    payload = {'msg': 'ok', 'room': 'r', 'sender': 's', 'json': {'chat_id': 'allowed-only', 'user_id': '1', 'id': '1', 'type': 1}}
    event = adapter._payload_to_message_event(payload)
    handled = asyncio.run(adapter._handle_inbound_event(event))
    assert handled is True
    assert len(emitted) == 1
    assert emitted[0].source.chat_id == 'allowed-only'

def test_handle_inbound_event_blocks_unregistered_room(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'allowed_chat_ids': ['allowed-only']}))
    emitted = []
    sent = []

    async def capture_message(event):
        emitted.append(event)
    adapter.handle_message = capture_message

    async def fake_send(chat_id, content, **kw):
        sent.append((chat_id, content))
        from gateway.platforms.base import SendResult
        return SendResult(success=True)
    adapter.send = fake_send
    payload = {'msg': 'hello', 'room': 'r', 'sender': 's', 'json': {'chat_id': 'blocked', 'user_id': '2', 'id': '2', 'type': 1}}
    event = adapter._payload_to_message_event(payload)
    handled = asyncio.run(adapter._handle_inbound_event(event))
    assert handled is False
    assert emitted == []
    assert sent == []

def test_handle_inbound_event_cr_replies_chat_id_in_allowed_room(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'allowed_chat_ids': ['allowed-only']}))
    emitted = []
    sent = []

    async def fake_send(chat_id, content, **kw):
        sent.append((chat_id, content))
        from gateway.platforms.base import SendResult
        return SendResult(success=True)

    async def capture_message(event):
        emitted.append(event)
    adapter.handle_message = capture_message
    adapter.send = fake_send
    payload = {'msg': '!cr', 'room': 'allowed-only', 'sender': 's', 'json': {'chat_id': 'allowed-only', 'user_id': '2', 'id': '3', 'type': 1}}
    event = adapter._payload_to_message_event(payload)
    handled = asyncio.run(adapter._handle_inbound_event(event))
    assert handled is True
    assert emitted == []
    assert sent == [('allowed-only', 'allowed-only')]

def test_handle_inbound_event_cr_replies_chat_id(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'allowed_chat_ids': ['allowed-only']}))
    emitted = []
    sent = []

    async def fake_send(chat_id, content, **kw):
        sent.append((chat_id, content))
        from gateway.platforms.base import SendResult
        return SendResult(success=True)

    async def capture_message(event):
        emitted.append(event)
    adapter.handle_message = capture_message
    adapter.send = fake_send
    payload = {'msg': '!cr', 'room': 'new-room', 'sender': 's', 'json': {'chat_id': '999888777', 'user_id': '2', 'id': '3', 'type': 1}}
    event = adapter._payload_to_message_event(payload)
    handled = asyncio.run(adapter._handle_inbound_event(event))
    assert handled is True
    assert emitted == []
    assert sent == [('999888777', '999888777')]

def test_handle_inbound_event_adcr_registers_and_replies(monkeypatch, tmp_path):
    from plugins.platforms.iris.adapter import IrisAdapter
    import yaml
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    config_path = tmp_path / 'config.yaml'
    config_path.write_text('gateway:\n  platforms:\n    iris:\n      extra: {}\n')
    adapter = IrisAdapter(DummyConfig({'config_path': str(config_path)}))
    emitted = []
    sent = []

    async def capture_message(event):
        emitted.append(event)

    async def fake_send(chat_id, content, **kw):
        sent.append((chat_id, content))
        from gateway.platforms.base import SendResult
        return SendResult(success=True)
    adapter.handle_message = capture_message
    adapter.send = fake_send
    payload = {'msg': '!adcr', 'room': 'new-room', 'sender': 'admin', 'json': {'chat_id': '555666777', 'user_id': '9', 'id': '10', 'type': 1}}
    event = adapter._payload_to_message_event(payload)
    handled = asyncio.run(adapter._handle_inbound_event(event))
    assert handled is True
    assert emitted == []
    assert len(sent) == 1
    assert sent[0][0] == '555666777'
    assert '등록 완료' in sent[0][1]
    assert '555666777' in sent[0][1]
    assert adapter._is_allowed_chat('555666777') is True
    saved = yaml.safe_load(config_path.read_text())
    assert saved['gateway']['platforms']['iris']['extra']['allowed_chat_ids'] == ['555666777']

def test_send_text_via_reply(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            assert url == 'http://127.0.0.1:3000/reply'
            assert json == {'type': 'text', 'room': 'chat-99', 'data': 'hello'}
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    result = asyncio.run(adapter.send('chat-99', 'hello'))
    assert result.success is True

def test_send_image_via_reply(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    import base64
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    posted = []

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted.append(json)
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    raw = b'fake-image'
    result = asyncio.run(adapter.send_image('room-1', raw))
    assert result.success is True
    assert len(posted) == 1
    assert posted[0]['type'] == 'image'
    assert posted[0]['room'] == 'room-1'
    assert posted[0]['data'] == base64.b64encode(raw).decode()

def test_standalone_send(monkeypatch):
    from plugins.platforms.iris.adapter import _standalone_send
    monkeypatch.setenv('IRIS_HOST', '10.0.0.5')
    monkeypatch.setenv('IRIS_PORT', '3000')

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            assert url == 'http://10.0.0.5:3000/reply'
            assert json['room'] == 'cron-room'
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    result = asyncio.run(_standalone_send(DummyConfig(), 'cron-room', 'cron message'))
    assert result.get('success') is True
    assert result.get('platform') == 'iris'

def test_env_enablement(monkeypatch):
    from plugins.platforms.iris.adapter import _env_enablement
    for k in ('IRIS_HOST', 'IRIS_PORT', 'IRIS_BASE_URL', 'IRIS_ALLOWED_CHAT_IDS', 'IRIS_HOME_CHANNEL'):
        monkeypatch.delenv(k, raising=False)
    assert _env_enablement() is None
    monkeypatch.setenv('IRIS_HOST', '192.168.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    monkeypatch.setenv('IRIS_ALLOWED_CHAT_IDS', 'a,b')
    seed = _env_enablement()
    assert seed['host'] == '192.168.0.1'
    assert seed['port'] == '3000'
    assert seed['allowed_chat_ids'] == ['a', 'b']
    assert seed['home_channel']['chat_id'] == 'a'

def test_check_reaction_disabled_by_default(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.delenv('IRIS_CHECK_REACTION', raising=False)
    adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000, 'check_reaction': True}))
    assert adapter._check_reaction_enabled is False

def test_check_reaction_enabled_via_env(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    for value in ('true', '1', 'yes', 'on', 'TRUE'):
        monkeypatch.setenv('IRIS_CHECK_REACTION', value)
        adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000}))
        assert adapter._check_reaction_enabled is True, value
    for value in ('false', '0', 'no', 'off', ''):
        monkeypatch.setenv('IRIS_CHECK_REACTION', value)
        adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000}))
        assert adapter._check_reaction_enabled is False, value

def test_send_document_routes_image_to_image_reply(monkeypatch, tmp_path):
    from plugins.platforms.iris.adapter import IrisAdapter
    import base64
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    image_file = tmp_path / 'photo.png'
    image_file.write_bytes(b'png-bytes')
    posted = []

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted.append(json)
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    result = asyncio.run(adapter.send_document('room-1', str(image_file)))
    assert result.success is True
    assert len(posted) == 1
    assert posted[0]['type'] == 'image'
    assert posted[0]['data'] == base64.b64encode(b'png-bytes').decode()

def test_send_document_non_image_text_fallback(monkeypatch, tmp_path):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    doc_file = tmp_path / 'report.pdf'
    doc_file.write_bytes(b'%PDF-1.4')
    posted = []

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted.append(json)
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    result = asyncio.run(adapter.send_document('room-2', str(doc_file), caption='첨부', file_name='report.pdf'))
    assert result.success is True
    assert len(posted) == 1
    assert posted[0]['type'] == 'text'
    assert 'report.pdf' in posted[0]['data']
    assert '첨부' in posted[0]['data']
    assert '이미지 외 파일 전송' in posted[0]['data']

def test_send_document_text_file_inlines_content(monkeypatch, tmp_path):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    text_file = tmp_path / 'notes.txt'
    text_file.write_text('hello from file\nline 2', encoding='utf-8')
    posted = []

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted.append(json)
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    result = asyncio.run(adapter.send_document('room-3', str(text_file), caption='메모'))
    assert result.success is True
    assert len(posted) == 1
    assert posted[0]['type'] == 'text'
    assert 'hello from file' in posted[0]['data']
    assert 'line 2' in posted[0]['data']
    assert '메모' in posted[0]['data']

def test_send_multiple_images_via_image_multiple(monkeypatch, tmp_path):
    from plugins.platforms.iris.adapter import IrisAdapter
    import base64
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    img1 = tmp_path / 'a.jpg'
    img2 = tmp_path / 'b.jpg'
    img1.write_bytes(b'img-a')
    img2.write_bytes(b'img-b')
    posted = []

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted.append(json)
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    asyncio.run(adapter.send_multiple_images('room-3', [(f'file://{img1}', ''), (f'file://{img2}', 'alt')]))
    assert len(posted) == 1
    assert posted[0]['type'] == 'image_multiple'
    assert posted[0]['room'] == 'room-3'
    assert posted[0]['data'] == [base64.b64encode(b'img-a').decode(), base64.b64encode(b'img-b').decode()]

def test_payload_to_message_event_file(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    payload = {'msg': '', 'room': '파일방', 'sender': '이영희', 'json': {'chat_id': '222', 'user_id': '333', 'id': 'file-1', 'type': 18, 'attachment': '{"name": "notes.txt", "size": 1024, "url": "https://dn-m.talk.kakao.com/files/abc"}'}}
    event = adapter._payload_to_message_event(payload)
    assert event is not None
    assert event.message_type == MessageType.DOCUMENT
    assert len(event.media_urls) == 1
    assert event.media_urls[0] == 'https://dn-m.talk.kakao.com/files/abc'
    assert event.media_types[0] == 'application/octet-stream'

def test_build_message_event_caches_inbound_file(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())

    async def fake_cache(url, display_name='file', kind='auto', content_type='application/octet-stream'):
        return {'path': '/tmp/cached/notes.txt', 'kind': 'file', 'display_name': display_name, 'media_type': content_type}
    monkeypatch.setattr(iris_adapter, 'cache_inbound_media_url', fake_cache)
    payload = {'msg': '', 'room': '파일방', 'sender': '이영희', 'json': {'chat_id': '222', 'user_id': '333', 'id': 'file-1', 'type': 18, 'attachment': '{"name": "notes.txt", "size": 1024, "url": "https://dn-m.talk.kakao.com/files/abc"}'}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event is not None
    assert event.message_type == MessageType.DOCUMENT
    assert event.media_urls == ['/tmp/cached/notes.txt']
    assert event.media_types == ['application/octet-stream']

def test_build_message_event_caches_inbound_image(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())

    async def fake_cache(url, display_name='file', kind='auto', content_type='application/octet-stream'):
        return {'path': '/tmp/cached/photo.jpg', 'kind': 'image', 'display_name': display_name, 'media_type': 'image/jpeg'}
    monkeypatch.setattr(iris_adapter, 'cache_inbound_media_url', fake_cache)
    payload = {'msg': '', 'room': '사진방', 'sender': '김철수', 'json': {'chat_id': '111', 'user_id': '222', 'id': 'img-1', 'type': 27, 'attachment': '{"imageUrls": ["https://example.com/a.jpg"]}'}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event is not None
    assert event.message_type in (MessageType.IMAGE, MessageType.PHOTO)
    assert event.media_urls == ['/tmp/cached/photo.jpg']
    assert event.media_types == ['image/jpeg']

def test_chat_log_row_to_reply_context_file():
    from plugins.platforms.iris.adapter import chat_log_row_to_reply_context
    ctx = chat_log_row_to_reply_context({'id': '300', 'message': '', 'type': 18, 'attachment': '{"name": "data.csv", "url": "https://dn-m.talk.kakao.com/files/data"}'})
    assert ctx['reply_to_text'] == '[파일: data.csv]'
    assert ctx['quoted_media_urls'] == ['https://dn-m.talk.kakao.com/files/data']
    assert ctx['quoted_media_kinds'] == ['file']
    assert ctx['quoted_media_names'] == ['data.csv']

def test_standalone_send_with_media_files(monkeypatch, tmp_path):
    from plugins.platforms.iris.adapter import _standalone_send
    import base64
    monkeypatch.setenv('IRIS_HOST', '10.0.0.5')
    monkeypatch.setenv('IRIS_PORT', '3000')
    image_file = tmp_path / 'cron.png'
    image_file.write_bytes(b'cron-img')
    posted = []

    class FakeResponse:
        status_code = 200
        text = 'ok'

    class FakeClient:

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            posted.append(json)
            return FakeResponse()
    monkeypatch.setattr('plugins.platforms.iris.adapter.httpx.AsyncClient', lambda **kw: FakeClient())
    result = asyncio.run(_standalone_send(DummyConfig(), 'cron-room', 'cron message', media_files=[str(image_file)]))
    assert result.get('success') is True
    assert len(posted) == 2
    assert posted[0]['type'] == 'text'
    assert posted[1]['type'] == 'image'
    assert posted[1]['data'] == base64.b64encode(b'cron-img').decode()

def test_send_returns_message_id(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())

    async def fake_post(payload):
        return True
    adapter._post_reply = fake_post
    result = asyncio.run(adapter.send('room-1', 'hello'))
    assert result.success is True
    assert result.message_id == 'iris-out-1'

def test_edit_message_enables_tool_progress(monkeypatch):
    from gateway.platforms.base import BasePlatformAdapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    assert IrisAdapter.edit_message is not BasePlatformAdapter.edit_message
    sent = []

    async def fake_post(payload):
        sent.append(payload)
        return True
    adapter._post_reply = fake_post
    first = asyncio.run(adapter.edit_message('room-1', 'prog-1', '🔍 web_search: "test"'))
    second = asyncio.run(adapter.edit_message('room-1', 'prog-1', '🔍 web_search: "test"'))
    assert first.success is True
    assert first.message_id == 'iris-out-1'
    assert second.success is True
    assert second.message_id == 'prog-1'
    assert len(sent) == 1

def test_payload_to_message_event_type2_single_photo(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    payload = {'msg': '', 'room': '사진방', 'sender': '김철수', 'json': {'chat_id': '111', 'user_id': '222', 'id': 'img-2', 'type': 2, 'attachment': '{"url": "//dn-m.talk.kakao.com/photo.jpg"}'}}
    event = adapter._payload_to_message_event(payload)
    assert event is not None
    assert event.message_type in (MessageType.IMAGE, MessageType.PHOTO)
    assert event.media_urls == ['https://dn-m.talk.kakao.com/photo.jpg']

def test_build_message_event_adds_attachment_context(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())

    async def fake_cache(url, display_name='file', kind='auto', content_type='application/octet-stream'):
        return {'path': '/tmp/cached/photo.jpg', 'kind': 'image', 'display_name': display_name, 'media_type': 'image/jpeg'}
    monkeypatch.setattr(iris_adapter, 'cache_inbound_media_url', fake_cache)
    payload = {'msg': '이거 봐줘', 'room': '사진방', 'sender': '김철수', 'json': {'chat_id': '111', 'user_id': '222', 'id': 'img-3', 'type': 27, 'attachment': '{"imageUrls": ["https://example.com/a.jpg"]}'}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert '[첨부 #1' in event.text
    assert '/tmp/cached/photo.jpg' in event.text
    assert '이거 봐줘' in event.text

def test_build_message_event_video_attachment(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())

    async def fake_cache(url, display_name='file', kind='auto', content_type='application/octet-stream'):
        return {'path': '/tmp/cached/video.mp4', 'kind': 'file', 'display_name': display_name, 'media_type': 'video/mp4'}
    monkeypatch.setattr(iris_adapter, 'cache_inbound_media_url', fake_cache)
    payload = {'msg': '', 'room': '영상방', 'sender': '김철수', 'json': {'chat_id': '111', 'user_id': '222', 'id': 'vid-1', 'type': 3, 'attachment': '{"url": "/video/path.mp4"}'}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event.message_type == MessageType.VIDEO
    assert event.media_urls == ['/tmp/cached/video.mp4']
    assert '[첨부 #1' in event.text

def test_should_fetch_long_message_text_at_3900_chars():
    from plugins.platforms.iris.kakao_payload import should_fetch_long_message_text
    preview = '가' * 3900
    attachment = '{"path": "talk/long/msg.txt"}'
    assert should_fetch_long_message_text(preview, attachment, msg_type=1) is True

def test_should_fetch_long_message_text_false_below_threshold():
    from plugins.platforms.iris.kakao_payload import should_fetch_long_message_text
    preview = '가' * 3899
    attachment = '{"path": "talk/long/msg.txt"}'
    assert should_fetch_long_message_text(preview, attachment, msg_type=1) is False

def test_should_fetch_long_message_text_false_without_path():
    from plugins.platforms.iris.kakao_payload import should_fetch_long_message_text
    preview = '가' * 3900
    assert should_fetch_long_message_text(preview, '{}', msg_type=1) is False

def test_should_fetch_long_message_text_false_for_image_type():
    from plugins.platforms.iris.kakao_payload import should_fetch_long_message_text
    preview = '가' * 3900
    attachment = '{"path": "talk/photo.jpg", "url": "//dn-m.talk.kakao.com/photo.jpg"}'
    assert should_fetch_long_message_text(preview, attachment, msg_type=2) is False

def test_build_message_event_fetches_long_message_text(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    preview = '가' * 3900
    full_text = '가' * 5000 + '\n전문 끝'

    async def fake_fetch(url):
        assert url == 'https://dn-m.talk.kakao.com/talk/long/msg.txt'
        return full_text
    monkeypatch.setattr(iris_adapter, 'fetch_long_message_text', fake_fetch)
    payload = {'msg': preview, 'room': '장문방', 'sender': '김철수', 'json': {'chat_id': '111', 'user_id': '222', 'id': 'long-1', 'type': 1, 'message': preview, 'attachment': '{"path": "talk/long/msg.txt"}'}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event.text == full_text
    assert len(event.text) > 3900

def test_build_message_event_long_message_fetch_failure_keeps_preview(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig())
    preview = '나' * 3900

    async def fake_fetch(url):
        return None
    monkeypatch.setattr(iris_adapter, 'fetch_long_message_text', fake_fetch)
    payload = {'msg': preview, 'room': '장문방', 'sender': '김철수', 'json': {'chat_id': '111', 'user_id': '222', 'id': 'long-2', 'type': 1, 'message': preview, 'attachment': '{"path": "talk/long/msg.txt"}'}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event.text == preview

def test_extract_v_origin_and_skip_sync():
    from plugins.platforms.iris.kakao_payload import extract_v_origin, should_skip_by_v_origin, should_skip_self_by_v_origin
    assert extract_v_origin('{"enc": 30, "origin": "MSG"}') == 'MSG'
    assert extract_v_origin('{"enc": 30, "origin": "WRITE"}') == 'WRITE'
    assert should_skip_by_v_origin('{"enc": 30, "origin": "SYNCMSG"}') is True
    assert should_skip_by_v_origin('{"enc": 30, "origin": "MCHATLOGS"}') is True
    assert should_skip_by_v_origin('{"enc": 30, "origin": "MSG"}') is False
    assert should_skip_self_by_v_origin('{"enc": 30, "origin": "WRITE"}') is True
    assert should_skip_self_by_v_origin('{"enc": 30, "origin": "MSG"}') is False

def test_predict_action_from_v_origin_msg_text():
    from plugins.platforms.iris.kakao_payload import predict_action_from_row
    action = predict_action_from_row('{"enc": 30, "origin": "MSG"}', msg_type=1, message='안녕하세요')
    assert action == 'INBOUND_TEXT'

def test_predict_action_from_v_origin_syncmsg_skips():
    from plugins.platforms.iris.kakao_payload import predict_action_from_row
    assert predict_action_from_row('{"enc": 30, "origin": "SYNCMSG"}', 1, 'sync') == 'SKIP_SYNC'

def test_predict_action_from_v_origin_write_skips_self():
    from plugins.platforms.iris.kakao_payload import predict_action_from_row
    assert predict_action_from_row('{"enc": 30, "origin": "WRITE"}', 1, 'bot msg') == 'SKIP_SELF'

def test_predict_action_from_v_origin_image():
    from plugins.platforms.iris.kakao_payload import predict_action_from_row
    action = predict_action_from_row('{"enc": 30, "origin": "MSG"}', msg_type=2, message='', attachment='{"url": "//dn-m.talk.kakao.com/photo.jpg"}')
    assert action == 'ANALYZE_IMAGE'

def test_predict_action_from_v_origin_long_text():
    from plugins.platforms.iris.kakao_payload import predict_action_from_row
    preview = '가' * 3900
    action = predict_action_from_row('{"enc": 30, "origin": "MSG"}', msg_type=1, message=preview, attachment='{"path": "talk/long/msg.txt"}')
    assert action == 'FETCH_LONG_TEXT'

def test_predict_action_from_v_origin_feed():
    from plugins.platforms.iris.kakao_payload import predict_action_from_row
    action = predict_action_from_row('{"enc": 30, "origin": "MSG"}', msg_type=0, message='{"feedType": 2}')
    assert action == 'PARSE_FEED'

def test_map_link_member_type():
    from plugins.platforms.iris.participant import map_link_member_type
    assert map_link_member_type(1) == 'HOST'
    assert map_link_member_type(2) == 'NORMAL'
    assert map_link_member_type(4) == 'MANAGER'
    assert map_link_member_type(8) == 'BOT'
    assert map_link_member_type(99) == 'UNKNOWN'

def test_member_type_query_skips_real_profile_user():
    from plugins.platforms.iris.participant import member_type_query_for_user
    assert member_type_query_for_user('443332129', 'room-1') is None
    assert member_type_query_for_user('99999999999', 'room-1') is not None

def test_query_sender_member_type_returns_none_for_real_profile_user():
    from plugins.platforms.iris.participant import query_sender_member_type

    async def fail_query(query, bind=None):
        raise AssertionError('open_chat_member query should not run for real profile users')
    member_type = asyncio.run(query_sender_member_type(fail_query, chat_id='room-1', user_id='443332129'))
    assert member_type is None

def test_query_sender_member_type_returns_none_when_open_chat_row_missing():
    from plugins.platforms.iris.participant import query_sender_member_type

    async def empty_query(query, bind=None):
        return []
    member_type = asyncio.run(query_sender_member_type(empty_query, chat_id='room-1', user_id='99999999999'))
    assert member_type is None

def test_user_id_filter_disabled_allows_any_user(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    monkeypatch.delenv('IRIS_USER_ID_FILTER', raising=False)
    adapter = IrisAdapter(DummyConfig({'allowed_chat_ids': ['room-1']}))
    assert adapter._is_allowed_user('999') is True
    assert adapter._is_allowed_inbound('room-1', '999') is True

def test_user_id_filter_blocks_disallowed_user(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'allowed_chat_ids': ['room-1'], 'allowed_user_ids': ['user-a'], 'user_id_filter_enabled': True}))
    assert adapter._is_allowed_inbound('room-1', 'user-a') is True
    assert adapter._is_allowed_inbound('room-1', 'user-b') is False
    assert adapter._is_allowed_inbound('room-2', 'user-a') is False

def test_handle_inbound_event_user_id_filter(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'allowed_chat_ids': ['room-1'], 'allowed_user_ids': ['allowed-user'], 'user_id_filter_enabled': True}))
    emitted = []

    async def capture_message(event):
        emitted.append(event)
    adapter.handle_message = capture_message
    allowed_payload = {'msg': 'ok', 'room': 'r', 'sender': 's', 'json': {'chat_id': 'room-1', 'user_id': 'allowed-user', 'id': '1', 'type': 1}}
    blocked_payload = {'msg': 'no', 'room': 'r', 'sender': 's', 'json': {'chat_id': 'room-1', 'user_id': 'other-user', 'id': '2', 'type': 1}}
    allowed_event = adapter._payload_to_message_event(allowed_payload)
    blocked_event = adapter._payload_to_message_event(blocked_payload)
    assert asyncio.run(adapter._handle_inbound_event(allowed_event)) is True
    assert asyncio.run(adapter._handle_inbound_event(blocked_event)) is False
    assert len(emitted) == 1

def test_build_message_event_attaches_sender_context(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'bot_id': '100'}))

    async def fake_query(query, bind=None):
        if 'link_member_type' in query and 'open_chat_member' in query:
            return [{'link_member_type': 4}]
        if 'original_profile_image_url' in query:
            return [{'original_profile_image_url': 'https://example.com/av.jpg'}]
        return []

    async def fake_cache(url, display_name='file', kind='auto', content_type='application/octet-stream'):
        return {'path': '/tmp/cached/avatar.jpg', 'kind': 'image', 'display_name': display_name, 'media_type': 'image/jpeg'}
    monkeypatch.setattr(adapter, '_iris_query', fake_query)
    monkeypatch.setattr(iris_adapter, 'cache_inbound_media_url', fake_cache)
    payload = {'msg': 'hello', 'room': '방', 'sender': '관리자', 'json': {'chat_id': '111', 'user_id': '99999999999', 'id': 'm-1', 'type': 1}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert event.extra['sender_member_type'] == 'MANAGER'
    assert event.extra['sender_avatar_url'] == 'https://example.com/av.jpg'
    assert event.extra['sender_avatar_path'] == '/tmp/cached/avatar.jpg'

def test_build_message_event_extra_works_without_dataclass_field(monkeypatch):
    from plugins.platforms.iris.adapter import IrisAdapter, ensure_message_event_extra
    from gateway.platforms.base import MessageEvent, MessageType

    class LegacyMessageEvent:

        def __init__(self):
            self.text = 'hi'
            self.message_type = MessageType.TEXT
            self.source = None
    event = LegacyMessageEvent()
    extra = ensure_message_event_extra(event)
    extra['sender_member_type'] = 'HOST'
    assert event.extra['sender_member_type'] == 'HOST'

def test_build_message_event_omits_member_type_for_real_profile_user(monkeypatch):
    from plugins.platforms.iris import adapter as iris_adapter
    from plugins.platforms.iris.adapter import IrisAdapter
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(DummyConfig({'host': '127.0.0.1', 'port': 3000}))

    async def fake_query(query, bind=None):
        if 'link_member_type' in query and 'open_chat_member' in query:
            raise AssertionError('real profile users should not query open_chat_member')
        if 'o_profile_image_url' in query:
            return [{'o_profile_image_url': 'https://example.com/real.jpg'}]
        return []
    monkeypatch.setattr(adapter, '_iris_query', fake_query)
    monkeypatch.setattr(iris_adapter, 'cache_inbound_media_url', AsyncMock(return_value=None))
    payload = {'msg': 'hello', 'room': '일반방', 'sender': '친구', 'json': {'chat_id': '111', 'user_id': '443332129', 'id': 'm-2', 'type': 1}}
    event = asyncio.run(adapter._build_message_event(payload))
    assert 'sender_member_type' not in event.extra
    assert event.extra['sender_avatar_url'] == 'https://example.com/real.jpg'
