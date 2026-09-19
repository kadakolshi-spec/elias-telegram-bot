import os
import unittest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from telethon.errors import FloodWaitError
import bot


class MemoryTests(unittest.TestCase):
    def test_isolation_bounds_reset_expiry(self):
        mem = bot.Memory(capacity=2, turns=1, ttl=10)
        with patch('bot.monotonic', return_value=0):
            mem.save(1, ['old', 'user', 'assistant'])
            mem.save(2, ['second'])
            self.assertEqual(mem.history(1), ['user', 'assistant'])
            self.assertEqual(mem.history(2), ['second'])
            mem.save(3, ['third'])
            self.assertEqual(mem.history(1), [])
            mem.reset(2)
            self.assertEqual(mem.history(2), [])
        with patch('bot.monotonic', return_value=11):
            self.assertEqual(mem.history(3), [])

    def test_required_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'TELEGRAM_API_ID'):
                bot.configuration()

    def test_user_global_and_flood_limits(self):
        limiter = bot.RateLimiter()
        with patch('bot.monotonic', return_value=0):
            self.assertTrue(limiter.allow(1))
            self.assertFalse(limiter.allow(1))
        for now in [3, 6, 9, 12]:
            with patch('bot.monotonic', return_value=now):
                self.assertTrue(limiter.allow(1))
        with patch('bot.monotonic', return_value=15):
            self.assertFalse(limiter.allow(1))
            for uid in range(2, 17):
                self.assertTrue(limiter.allow(uid))
            self.assertFalse(limiter.allow(99))
        with patch('bot.monotonic', return_value=100):
            self.assertTrue(limiter.allow(1))
            limiter.pause(30)
        with patch('bot.monotonic', return_value=120):
            self.assertFalse(limiter.allow(2))
        with patch('bot.monotonic', return_value=132):
            self.assertTrue(limiter.allow(2))


class ChatTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.create = AsyncMock(return_value=SimpleNamespace(output_text='Hey there!'))
        self.ai = SimpleNamespace(responses=SimpleNamespace(create=self.create))
        self.elias = bot.Elias(self.ai, 10, datetime.now(timezone.utc) - timedelta(seconds=1))
        self.event = SimpleNamespace(sender_id=42, id=1, is_private=True, out=False,
            raw_text='Hello', message=SimpleNamespace(date=datetime.now(timezone.utc)),
            get_sender=AsyncMock(return_value=SimpleNamespace(bot=False, deleted=False)), reply=AsyncMock())

    async def test_roundtrip_context_and_reset(self):
        with patch('bot.monotonic', return_value=100):
            await self.elias.handle(self.event)
        self.event.reply.assert_awaited_with('Hey there!', parse_mode=None, link_preview=False)
        self.assertFalse(self.create.call_args.kwargs['store'])
        self.event.raw_text, self.event.id = 'Remember me?', 2
        with patch('bot.monotonic', return_value=104):
            await self.elias.handle(self.event)
        sent = self.create.call_args.kwargs['input']
        self.assertEqual(sent[0]['content'], 'Hello')
        self.assertEqual(sent[1]['content'], 'Hey there!')
        self.assertEqual(self.elias.memory.history(99), [])
        self.event.raw_text, self.event.id = '/reset', 3
        with patch('bot.monotonic', return_value=108):
            await self.elias.handle(self.event)
        self.assertEqual(self.elias.memory.history(42), [])

    async def test_groups_outgoing_self_service_old_and_bots_ignored(self):
        for field, value in [('is_private', False), ('out', True), ('sender_id', 10), ('sender_id', 777000), ('raw_text', '')]:
            old = getattr(self.event, field)
            setattr(self.event, field, value)
            await self.elias.handle(self.event)
            setattr(self.event, field, old)
        self.event.message.date = self.elias.ready_at - timedelta(seconds=1)
        await self.elias.handle(self.event)
        self.event.message.date = datetime.now(timezone.utc)
        self.event.get_sender.return_value.bot = True
        await self.elias.handle(self.event)
        self.create.assert_not_awaited()
        self.event.reply.assert_not_awaited()

    async def test_duplicate_and_busy_dropped(self):
        await self.elias.handle(self.event)
        await self.elias.handle(self.event)
        self.assertEqual(self.create.await_count, 1)
        self.event.id = 2
        self.elias.busy.add(42)
        await self.elias.handle(self.event)
        self.assertEqual(self.create.await_count, 1)

    async def test_api_failure_no_secrets_or_context(self):
        self.create.side_effect = RuntimeError('secret must never be logged')
        with self.assertLogs('elias', level='WARNING') as logs:
            await self.elias.handle(self.event)
        self.assertNotIn('secret', ''.join(logs.output))
        self.assertEqual(self.elias.memory.history(42), [])
        self.event.reply.assert_not_awaited()
        self.assertEqual(self.elias.busy, set())

    async def test_flood_wait_blocks_other_users_without_retry(self):
        self.event.reply.side_effect = FloodWaitError(request=None, capture=60)
        with patch('bot.monotonic', return_value=100):
            await self.elias.handle(self.event)
            self.event.sender_id, self.event.id = 43, 2
            await self.elias.handle(self.event)
        self.assertEqual(self.event.reply.await_count, 1)
        self.assertEqual(self.create.await_count, 1)
        self.assertEqual(self.elias.memory.history(42), [])

    async def test_long_input_never_calls_api(self):
        self.event.raw_text = 'x' * 4001
        await self.elias.handle(self.event)
        self.create.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
