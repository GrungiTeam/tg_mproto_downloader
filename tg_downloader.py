#!/usr/bin/env python3

import os
import sys
import time
import asyncio
from typing import Union
from asyncio import Task
# Import the client

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.handlers import MessageHandler


class Downloader:

    def __init__(self, session: str, api_id: int, api_hash: str, bot_token: str, download_path: str,
                 parallel_downloads: int,
                 download_timeout: int,
                 authorized_users: list) -> None:
        self._session = session
        self._api_id = api_id
        self._api_hash = api_hash
        self._bot_token = bot_token
        self._download_path = download_path
        self._parallel_downloads = parallel_downloads
        self._download_timeout = download_timeout
        self._authorized_users = authorized_users
        self._create_workflow()

    def _clean_up(self) -> None:
        for task in self._tasks:
            task.cancel()

    def _create_workflow(self) -> None:
        self._queue = asyncio.Queue()
        self._tasks: list[Task] = []
        self._client = Client(self._session, self._api_id, self._api_hash, bot_token=self._bot_token)
        # Create worker tasks to process the queue concurrently.
        for i in range(self._parallel_downloads):
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._worker(f'worker-{i}'))
            self._tasks.append(task)

    def _update_progress(self, current: int, total: int, *args) -> None:
        reply: Message = args[0]
        quota = int(current * 100 / total)
        if quota % 10 != 0:
            return
        try:
            reply.edit(f"{quota}%")
        finally:
            pass

    async def _worker(self, name):
        while True:
            # Get a "work item" out of the queue.
            queue_item = await self._queue.get()
            message: Message = queue_item[0]
            reply: Message = queue_item[1]
            file_name = message.document.file_name if message.document else message.video.file_name
            file_path = os.path.join(self._download_path, file_name)
            await reply.edit('Downloading...')
            print("[%s] Download started at %s" % (file_name, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
            try:
                loop = asyncio.get_event_loop()
                task = loop.create_task(self._client.download_media(message, file_path, progress=self._update_progress,
                                                                    progress_args=[reply]))
                await asyncio.wait_for(task, timeout=self._download_timeout)
                end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                end_time_short = time.strftime("%H:%M", time.localtime())
                print("[%s] Successfully downloaded at %s" % (file_name, end_time))
                await reply.edit('Finished at %s' % end_time_short)
            except asyncio.TimeoutError:
                print("[%s] Timeout reached at %s" % (file_name, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
                await reply.edit('Error!')
                await message.reply_text('ERROR: Timeout reached downloading this file', quote=True)
            except Exception as e:
                print("[EXCEPTION]: %s" % (str(e)))
                # print("[%s]: %s" % (e.__class__.__name__, str(e)))
                print("[%s] Exception at %s" % (file_name, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
                await reply.edit('Error!')
                await message.reply_text(
                    'ERROR: Exception %s raised downloading this file: %s' % (e.__class__.__name__, str(e)), quote=True)

            # Notify the queue that the "work item" has been processed.
            self._queue.task_done()

    # This is our update handler. It is called when a new update arrives.
    async def _handler(self, client: Client, message: Message):
        if message.document or message.video is not None:
            print("Received media")
            file_name = message.document.file_name if message.document else message.video.file_name
            print("[%s] Download queued at %s" % (file_name, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())))
            reply = await message.reply_text('In queue', quote=True)
            await self._queue.put([message, reply])
        if message.text == "/cancel":
            self._clean_up()
            await message.reply_text("All downloads are has aborted")
            print("Aborted all active downloads")

    def run(self) -> None:
        try:
            msg_filter = filters.private
            if self._authorized_users:
                msg_filter = filters.private & filters.user(users=self._authorized_users)
            handler = MessageHandler(self._handler, msg_filter)
            # Register the update handler so that it gets called
            self._client.add_handler(handler)
            # Run the client until Ctrl+C is pressed, or the client disconnects
            print('Successfully started (Press Ctrl+C to stop)')
            self._client.run()
        finally:
            # Cancel our worker tasks.
            self._clean_up()
            # Stop Pyrogram client
            print('Stopped!')


# This is a helper method to access environment variables or
# prompt the user to type them in the terminal if missing.
def get_env(name: str, message: str, cast=str) -> Union[int, str]:
    if name in os.environ:
        return os.environ[name]
    while True:
        value = input(message)
        try:
            return cast(value)
        except ValueError as e:
            print(e, file=sys.stderr)
            time.sleep(1)


# Get information needed to run the bot
def init_settings() -> []:
    session = os.environ.get('TG_SESSION', 'tg_downloader')
    api_id = get_env('TG_API_ID', 'Enter your API ID: ', int)
    api_hash = get_env('TG_API_HASH', 'Enter your API hash: ')
    bot_token = get_env('TG_BOT_TOKEN', 'Enter your Telegram BOT token: ')
    download_path = get_env('TG_DOWNLOAD_PATH', 'Enter full path to downloads directory: ')
    parallel_downloads = int(os.environ.get('TG_MAX_PARALLEL', 4))
    download_timeout = int(os.environ.get('TG_DL_TIMEOUT', 5400))
    authorized_users = get_env('TG_AUTHORIZED_USER_ID',
                               "Enter the list authorized users' id (separated by comma, empty for any): ")
    authorized_users = [int(user_id) for user_id in authorized_users.split(",")] if authorized_users else []
    return session, api_id, api_hash, bot_token, download_path, parallel_downloads, download_timeout, authorized_users


def main() -> None:
    # Create instance of Downloader
    downloader = Downloader(*init_settings())
    downloader.run()


if __name__ == '__main__':
    main()
