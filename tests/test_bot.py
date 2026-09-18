import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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

    def test_missing_secrets_fail_fast(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, 'TELEGRAM_BOT_TOKEN'):
                bot.build_app()


class ChatTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        bot.memory = bot.Memory()
        self.message = SimpleNamespace(text='Hello', reply_text=AsyncMock())
        self.update = SimpleNamespace(message=self.message,
            effective_user=SimpleNamespace(id=42, language_code='en'))
        self.create = AsyncMock(return_value=SimpleNamespace(output_text='Hey there!'))
        self.context = SimpleNamespace(bot_data={'openai': SimpleNamespace(
            responses=SimpleNamespace(create=self.create))})

    async def test_roundtrip_and_context(self):
        await bot.chat(self.update, self.context)
        self.message.reply_text.assert_awaited_with('Hey there!')
        self.assertFalse(self.create.call_args.kwargs['store'])
        self.message.text = 'Remember me?'
        await bot.chat(self.update, self.context)
        sent = self.create.call_args.kwargs['input']
        self.assertEqual(sent[0]['content'], 'Hello')
        self.assertEqual(sent[1]['content'], 'Hey there!')
        self.assertEqual(bot.memory.history(99), [])

    async def test_api_error_does_not_pollute_memory(self):
        self.create.side_effect = RuntimeError('secret must never be logged')
        with self.assertLogs('elias', level='WARNING') as logs:
            await bot.chat(self.update, self.context)
        self.assertNotIn('secret', ''.join(logs.output))
        self.assertEqual(bot.memory.history(42), [])
        self.assertIn('hiccup', self.message.reply_text.call_args.args[0])

    async def test_reset(self):
        await bot.chat(self.update, self.context)
        await bot.reset(self.update, self.context)
        self.assertEqual(bot.memory.history(42), [])

    async def test_long_input_never_calls_api(self):
        self.message.text = 'x' * 4001
        await bot.chat(self.update, self.context)
        self.create.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
