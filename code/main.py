import discord

from discord.ext import tasks
import os
from urlextract import URLExtract
from urllib.parse import urlparse
import asyncio

from ModerationEmbedClass import *
from typing import Union, Type


class MyBot(discord.Client):
    messages_cleanup_lock = asyncio.Lock
    lock_timeout_cleanup = asyncio.Lock
    lock_healthcheck = asyncio.Lock
    __connected: bool = False

    def __init__(self, intents: discord.Intents = None):
        intents.message_content = True
        super().__init__(intents=intents)
        self._set_as_disconnected()

        self.config = Config(
            messages_db=MessagesDB(),
            timeout_hours=5,
            moderation_roles=[int(role_id) for role_id in os.getenv("DISCORD_MODERATION_ROLES", "").split()],
            server_id=os.getenv("DISCORD_SERVER_ID")
        )

        self.messages_cleanup_lock = asyncio.Lock()
        self.lock_timeout_cleanup = asyncio.Lock()
        self.lock_healthcheck = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self.__connected

    def _set_as_connected(self):
        self.__connected = True

    def _set_as_disconnected(self):
        self.__connected = False

    async def on_resumed(self):
        self._set_as_connected()
        print("Reconnected!")

    async def on_connect(self):
        self._set_as_connected()
        print("Connected!")

    async def on_disconnect(self):
        self._set_as_disconnected()
        print("Disconnected!")

    async def on_ready(self):
        print(f'We have logged in as {client.user}')
        self.messages_cleanup.start()
        self.task_timeout_cleanup.start()
        self.task_check_health.start()

    async def on_message(self, message: discord.Message):
        print(self.config.server_id)
        if message.guild.id != int(self.config.server_id):
            print(f"Wrong server {message.author}")
        elif message.author.bot:
            pass  # Ignore bots
        elif not message.guild.id:
            pass  # Ignore messages without guild id
        else:
            extractor = URLExtract()

            urlextract = extractor.find_urls(message.content)
            sanitized_urls = [f"{urlparse(link).netloc}/{urlparse(link).path}" for link in urlextract]
            # Ignore cases where no links are provided.
            if len(sanitized_urls) > 0:
                message_object = MessageRecord(
                    id=message.id,
                    author_id=message.author.id,
                    server_id=message.guild.id,
                    creation_timestamp=message.created_at,
                    urls=sanitized_urls,
                    message_url=message.jump_url
                )
                self.config.messages_db.add_message(message_object)

                await self.review_user(message)

    async def review_user(self, message: discord.Message):
        author_messages_db: MessagesDBServerAuthor = self.config.messages_db.servers.get(message.guild.id).authors.get(
            message.author.id)

        global global_same_link_threshold

        def get_timeout_reason() -> None | ExceededSameLinkRateLimit | ExceededTotalLinksRateLimit:

            # sanitized_urls = []
            sanitized_urls = author_messages_db.get_uniq_urls()
            # Review user for same URL posted.
            i = 0
            while i < len(sanitized_urls):
                url: str = sanitized_urls[i]
                count = self.config.messages_db.count_links_from_author(
                    server_id=message.guild.id,
                    author_id=message.author.id,
                    timestamp=message.created_at,
                    url=url
                )
                print(f"User '{message.author.id}' Count '{count}' for URL '{url}'")
                if count > global_same_link_threshold:
                    return ExceededSameLinkRateLimit(urls=url)
                i += 1
            del url, count

            # Review user total URL posted.
            total_count = self.config.messages_db.count_total_sent_links_from_author(
                server_id=message.guild.id,
                author_id=message.author.id,
                timestamp=message.created_at
            )
            print(f"User '{message.author.id}' Total count '{total_count}'")
            if total_count > global_total_links_threshold:
                return ExceededTotalLinksRateLimit()

        moderation_status = ModerationStatus()
        moderation_status.users_to_mention = [self.get_user(int(message.guild.owner_id))]

        if author_messages_db.timed_out:
            print(
                f"Skipping checking user {message.author.id} due to existing in the cached timed out db ({message.author.name}|{message.author.display_name}|{message.author.global_name})")
        else:
            moderation_status.trigger_reason = get_timeout_reason()

        if moderation_status.trigger_reason:

            print(
                f"Timeout trigger! {moderation_status.trigger_reason}. User {message.author.name}. Reason {type(moderation_status.trigger_reason)}.")

            # if type(moderation_status.trigger_reason) is ExceededSameLinkRateLimit:
            #     print(f"user {message.author.name} triggered timeout with the url ??")
            # TODO cleanup this comments
            # 0. Check if user is timed out (to avoid further triggers)
            # if not message.author.is_timed_out():
            # 1. Timeout the user

            # failed_to_timeout = False
            try:
                if type(moderation_status.trigger_reason) is ExceededSameLinkRateLimit:
                    await message.author.timeout(datetime.timedelta(hours=self.config.timeout_hours),
                                                 reason=f"Triggered rate limit ({global_same_link_threshold} instances) with URL ??")
                else:  # ExceededTotalLinksRateLimit
                    await message.author.timeout(datetime.timedelta(hours=self.config.timeout_hours),
                                                 reason=f"Triggered rate limit ({global_total_links_threshold} instances) with URL multiple URLs")
                moderation_status.preemptive_timeout_applied = True
            except discord.errors.Forbidden:
                await message.channel.send(f"Missing permissions when timing out user {message.author.mention}")

            # Feedback/Message for the MODERATED USER
            await message.channel.send(content=f"# Preemptive timeout {message.author.mention}\n"
                                               f"## Timout hours: {self.config.timeout_hours}\n"
                                               f"If you believe this is was a mistake, please contact the "
                                               f"moderators/admins.\n")

            # 3 Message for the moderation team/channel
            moderation_channel = None
            if message.guild.public_updates_channel:
                moderation_channel = message.guild.public_updates_channel
            else:
                moderation_channel = message.channel

            author_messages_db.set_cache_timeout()
            moderation_buttons = ModerationEmbedClass(moderated_discord_user=message.author,
                                                      allowed_moderation_roles=self.config.moderation_roles,
                                                      config=self.config,
                                                      moderation_status=moderation_status,
                                                      discord_bot=self,
                                                      )

            await moderation_channel.send(
                content="\n".join(moderation_buttons.get_mentions())
            )

            try:
                await moderation_channel.send(
                    embed=moderation_buttons.get_status_embed(),
                    view=moderation_buttons,
                )
            except discord.errors.Forbidden:
                print(f"No permissions to send embeds to channel {moderation_channel.id}")
                moderation_buttons.embed_mode = False
                await moderation_channel.send(
                    content=moderation_buttons.get_status_text(),
                    view=moderation_buttons,
                )


            # 3. Remove recent messages  # Embed in the admins channel for admins to decide what to do with it?

    def get_recent_messages_from_user(self, user_id: int) -> list[MessageRecord]:
        for server in self.config.messages_db.servers.values():
            server: MessagesDBServer
            for author in server.authors.values():
                author: MessagesDBServerAuthor
                if author.id == user_id:
                    return author.messages

    @tasks.loop(seconds=5)
    async def messages_cleanup(self):
        async with self.messages_cleanup_lock:
            print("Messages cleanup job start")
            global global_thresholds_seconds
            job_start_timestamp = datetime.datetime.now(datetime.UTC)
            bottom_threshold = job_start_timestamp - datetime.timedelta(
                seconds=global_thresholds_seconds + 5)  # Adding an extra margin just in case
            for server in self.config.messages_db.servers.values():
                server: MessagesDBServer
                for author in server.authors.values():
                    author: MessagesDBServerAuthor
                    for message in author.messages:
                        message: MessageRecord
                        if message.creation_timestamp < bottom_threshold:
                            print(
                                f"[CACHE CLEANUP] Deleting message {message.id} from user {message.author_id} (server {message.server_id})")
                            author.messages.remove(message)

    @tasks.loop(seconds=15)
    async def task_timeout_cleanup(self):
        async with self.lock_timeout_cleanup:
            print("Timeout cleanup job start")
            job_start_timestamp = datetime.datetime.now(datetime.UTC)
            bottom_threshold = job_start_timestamp - datetime.timedelta(
                seconds=global_thresholds_seconds + 5)  # Adding an extra margin just in case
            for server in self.config.messages_db.servers.values():
                server: MessagesDBServer
                for author in server.authors.values():
                    author: MessagesDBServerAuthor
                    if author.timed_out and author.timed_out_timestamp < bottom_threshold:
                        author.clear_cache_timout()

    @tasks.loop(seconds=5)
    async def task_check_health(self):
        file = '/tmp/healthy'
        print(f"Is connected? {self.is_connected}")

        if self.is_connected:
            with open(file, "w") as f:
                f.write(("NOK", "OK")[self.is_connected])
        else:
            try:
                os.remove(file)
            except OSError:
                pass

            try:
                await self.connect()
            except Exception as e:
                print(f"Error while attempting to reconnect. \n{e}")


global_thresholds_seconds = 5  # Every when to clean up the internal cache/or also named as how wide is the margin.
global_same_link_threshold = 3  # Total number of hits (per used) allowed. Triggers at 4
global_total_links_threshold = 10  # Allowing a total of 10 links sent per used within 5 seconds. Triggers at 11

if __name__ == '__main__':
    _intents = discord.Intents.default()
    _intents.message_content = True
    _intents.members = True

    token = os.getenv("DISCORD_API_TOKEN")
    client = MyBot(_intents)
    client.run(token)
