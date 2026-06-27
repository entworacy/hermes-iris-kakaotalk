from pathlib import Path

def test_bundled_skill_names():
    from plugins.platforms.iris.skills_install import bundled_skill_names
    names = bundled_skill_names()
    assert 'iris-gateway' in names
    assert 'iris-chat-assistant' in names

def test_install_bundled_skills_copies_to_hermes_home(tmp_path, monkeypatch):
    from plugins.platforms.iris.skills_install import install_bundled_skills
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    installed = install_bundled_skills()
    assert 'iris-gateway' in installed
    assert 'iris-chat-assistant' in installed
    assert (tmp_path / 'skills' / 'iris-gateway' / 'SKILL.md').is_file()
    assert (tmp_path / 'skills' / 'iris-chat-assistant' / 'SKILL.md').is_file()
    again = install_bundled_skills()
    assert again == []

def test_register_plugin_skills_calls_ctx_register_skill():
    from unittest.mock import MagicMock
    from plugins.platforms.iris import register as plugin_register
    ctx = MagicMock()
    plugin_register(ctx)
    assert ctx.register_platform.called
    assert ctx.register_skill.call_count >= 2

def test_allowed_chat_sets_auto_skill(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from plugins.platforms.iris.adapter import IrisAdapter
    from gateway.platforms.base import MessageEvent, MessageType
    monkeypatch.setenv('IRIS_HOST', '127.0.0.1')
    monkeypatch.setenv('IRIS_PORT', '3000')
    adapter = IrisAdapter(type('Cfg', (), {'extra': {'host': '127.0.0.1', 'port': 3000, 'allowed_chat_ids': ['room-1']}})())
    adapter.handle_message = AsyncMock()
    event = MessageEvent(text='hello', message_type=MessageType.TEXT, source=adapter.build_source(chat_id='room-1', user_id='999', user_name='user'), message_id='1')
    asyncio.run(adapter._handle_inbound_event(event))
    assert event.auto_skill == 'iris-chat-assistant'
    adapter.handle_message.assert_awaited_once()
