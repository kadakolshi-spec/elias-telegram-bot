"""Run locally in a real terminal. Credentials never go to stdout or disk."""
import asyncio
import getpass
import logging
import sys
import warnings
import tkinter as tk
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession


def secret(prompt):
    # Refuse getpass's insecure fallback when no private terminal is available.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        return getpass.getpass(prompt).strip()


def copy_window(values):
    root = tk.Tk()
    root.title('Elias — Railway secrets (local only)')
    root.geometry('580x320')
    tk.Label(root, text='Session ready. Paste each value into Railway Variables.\n'
             'Values remain hidden and are not saved to disk.\n'
             'Keep this window open until all three values are saved.').pack(pady=18)
    status = tk.StringVar(value='Do not paste these values into chat.')
    copied = [None]
    def clear_clipboard():
        try:
            if copied[0] is not None and root.clipboard_get() == copied[0]:
                root.clipboard_clear()
        except tk.TclError:
            pass
        copied[0] = None
    def copy(name):
        clear_clipboard()
        root.clipboard_append(values[name])
        copied[0] = values[name]
        status.set(name + ' copied. Paste into Railway now.')
    def close():
        clear_clipboard()
        values.clear()
        root.destroy()
    for name in values:
        tk.Button(root, text='Copy ' + name, command=lambda n=name: copy(n)).pack(pady=5)
    tk.Label(root, textvariable=status).pack(pady=12)
    tk.Button(root, text='Done — clear clipboard and close', command=close).pack()
    root.protocol('WM_DELETE_WINDOW', close)
    root.mainloop()


async def generate():
    api_id = secret('TELEGRAM_API_ID (hidden): ')
    api_hash = secret('TELEGRAM_API_HASH (hidden): ')
    phone = secret('Elias phone number with country code (hidden): ')
    if not api_id.isdigit() or int(api_id) <= 0 or len(api_hash) != 32:
        raise ValueError('Invalid API credentials format')
    client = TelegramClient(StringSession(), int(api_id), api_hash,
                            device_model='Elias Session Setup',
                            flood_sleep_threshold=0, request_retries=0)
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        code = secret('Telegram login code (hidden): ')
        try:
            await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
        except SessionPasswordNeededError:
            await client.sign_in(password=secret('Telegram 2FA password (hidden): '))
        me = await client.get_me()
        if me is None or me.bot:
            raise ValueError('Normal user account required')
        session = client.session.save()
        return {'TELEGRAM_API_ID': api_id, 'TELEGRAM_API_HASH': api_hash,
                'TELEGRAM_SESSION': session}
    finally:
        await client.disconnect()


def main():
    logging.disable(logging.CRITICAL)
    if not sys.stdin.isatty():
        print('Open this script in your own terminal, not an agent tool or redirected console.')
        return 1
    # Check the local display before requesting a Telegram login code.
    probe = tk.Tk()
    probe.withdraw()
    probe.destroy()
    print('Elias local login. Input is hidden; no secret files are created.')
    try:
        values = asyncio.run(generate())
        copy_window(values)
        print('Setup closed. No secrets were printed or saved.')
        return 0
    except KeyboardInterrupt:
        print('Cancelled.')
    except Exception as exc:
        print('Setup failed (' + type(exc).__name__ + '). Check credentials or try later; no secret details logged.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
