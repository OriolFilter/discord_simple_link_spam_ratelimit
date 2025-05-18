# This example requires the 'message_content' intent.
import dataclasses
import datetime

import discord

# from discord import Message

from discord.ext.commands import Context
from discord.ext import tasks
from discord.ext.commands import Cog
import os
from urlextract import URLExtract
from urllib.parse import urlparse
import asyncio
from datetime import timezone


@dataclasses.dataclass
class MessageRecord:
    id: int
    author_id: int
    server_id: int
    creation_timestamp: datetime.datetime
    links: list[str]
    message_url: str


# Each user will have its own
class MessagesDBServerAuthor:
    messages: [MessageRecord]
    id: int
    lock: asyncio.Lock  # Used to avoid multiple instances of reviewing the user

    def __init__(self, id: int):
        self.messages = []
        self.lock = asyncio.Lock()
        self.id = int(id)

    def add_message(self, message_object: MessageRecord):
        self.messages.append(message_object)
        # print(f"Total messages from user {message_object.author_id} ({len(self.messages)})")

    def count_links_from_author(self, timestamp: datetime.datetime, url: str) -> int:
        count = 0
        for message in self.get_messages_within_threshold(timestamp):
            if url in message.links:
                count += 1
        return count

    def get_messages_within_threshold(self, top_timestamp_threshold: datetime.datetime) -> list[MessageRecord]:
        message_list = []
        for message in self.messages:
            message: MessageRecord
            global global_thresholds_seconds
            bottom_threshold = top_timestamp_threshold - datetime.timedelta(seconds=global_thresholds_seconds)

            if top_timestamp_threshold >= message.creation_timestamp >= bottom_threshold:
                message_list.append(message)
        return message_list


class MessagesDBServer:
    authors: {id: MessagesDBServerAuthor}

    def __init__(self):
        self.authors: dict[id: MessagesDBServerAuthor] = dict()

    def add_message(self, message_object: MessageRecord):
        if message_object.author_id not in self.authors.keys():
            self.authors[message_object.author_id] = MessagesDBServerAuthor(id=message_object.author_id)
        self.authors[message_object.author_id].add_message(message_object)

    def count_links_from_author(self, author_id: int, timestamp: datetime.datetime, url: str) -> int:
        if author_id not in self.authors.keys():
            return 0
        else:
            return self.authors[author_id].count_links_from_author(
                timestamp=timestamp,
                url=url
            )


class MessagesDB:
    servers: dict[id: MessagesDBServer]

    def __init__(self):
        self.servers: dict[id: MessagesDBServer] = dict()

    def add_message(self, message_object: MessageRecord):
        if message_object.server_id not in self.servers.keys():
            self.servers[message_object.server_id] = MessagesDBServer()
        self.servers[message_object.server_id].add_message(message_object)

    def count_links_from_author(self, server_id: int, author_id: int, timestamp: datetime.datetime, url: str) -> int:
        if server_id not in self.servers.keys():
            return 0
        else:
            return self.servers[server_id].count_links_from_author(
                author_id=author_id,
                timestamp=timestamp,
                url=url
            )


@dataclasses.dataclass
class Config:
    messages_db: MessagesDB
    timeout_hours: int
    roles_to_ping: list[str]
    moderation_channel_id: str
    server_id: str | None
    # thresholds_seconds: int
    # count_threshold: 5


class MyBot(discord.Client):
    lock = asyncio.Lock

    def __init__(self, intents: discord.Intents = None):
        intents.message_content = True
        super().__init__(intents=intents)

        # discord_moderation_channel_id = None
        # if os.getenv("DISCORD_MODERATION_CHANNEL_ID"):
        #     discord_moderation_channel_id = int(os.getenv("DISCORD_MODERATION_CHANNEL_ID"))

        self.config = Config(
            messages_db=MessagesDB(),
            timeout_hours=5,
            roles_to_ping=os.getenv("DISCORD_ROLES_TO_PING_ID", "").split(),
            moderation_channel_id=os.getenv("DISCORD_MODERATION_CHANNEL_ID", ""),
            server_id=os.getenv("DISCORD_SERVER_ID", "")
        )

        self.lock = asyncio.Lock()

    # @discord.ext. event
    async def on_ready(self):
        print(f'We have logged in as {client.user}')
        self.messages_cleanup.start()

    async def on_message(self, message: discord.Message):
        if message.guild.id != self.config.server_id:
            # Ignore other servers
            pass
        if message.author.bot:
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
                    links=sanitized_urls,
                    message_url=message.jump_url
                )
                self.config.messages_db.add_message(message_object)

                global global_count_threshold

                triggered_timeout: bool = False
                triggered_timeout_url: str|None = None

                i = 0
                while not triggered_timeout and i < len(sanitized_urls):
                    url: str = sanitized_urls[i]
                    count = self.config.messages_db.count_links_from_author(
                        server_id=message_object.server_id,
                        author_id=message_object.author_id,
                        timestamp=message_object.creation_timestamp,
                        url=url
                    )
                    print(f"Count {count} for URL '{url}'")
                    if count > global_count_threshold:
                        triggered_timeout = True
                        triggered_timeout_url = url
                    i += 1
                del url, count

                if triggered_timeout:
                    print(f"user {message.author.name} triggered timeout with the url {triggered_timeout_url}")

                    # 1. Timeout the user
                    failed_to_timeout = False
                    await message.channel.send(f"# Preemtive timeout {message.author.mention}\n"
                                               f"## Timout hours: {self.config.timeout_hours}\n"
                                               f"If you believe this is was an, please contact the "
                                               f"moderators/admins.\n")
                    try:
                        await message.author.timeout(datetime.timedelta(hours=self.config.timeout_hours),
                                                     reason=f"Triggered rate limit ({global_count_threshold} instances) with URL {triggered_timeout_url}")
                    except discord.errors.Forbidden:
                        failed_to_timeout = True
                        await message.channel.send("Missing permissions when timing out user")

                    # 3 Mention in the moderation_channel
                    # moderation_channel: discord.TextChannel | None = None
                    # for server in client.guilds:
                    #     server: discord.Guild
                    #     if int(server.id) == int(message.guild.id):
                    #         for channel in server.channels:
                    #             if channel.name == self.config.moderation_channel_name:
                    #                 moderation_channel = channel
                    # del server
                    # print(moderation_channel)

                    moderation_channel = None
                    if self.config.moderation_channel_id:
                        moderation_channel = self.get_channel(int(self.config.moderation_channel_id))

                    mod_pings = ""
                    if len(self.config.roles_to_ping) < 1:
                        server_owner = self.client.get_user(int(message.guild.owner_id))
                        mod_pings = f"\n++ {server_owner}"

                    else:
                        mod_pings = "\n++ ".join([f"<@&{role_id}>" for role_id in self.config.roles_to_ping])

                    # Messages currently stored from the user
                    possible_recent_messages_from_user: list[MessageRecord] = self.get_recent_messages_from_user(
                        message.author.id)
                    formated_list_possible_recent_messages_from_user = ""
                    for possible_message in possible_recent_messages_from_user:
                        possible_message: MessageRecord
                        formated_list_possible_recent_messages_from_user += f"- {possible_message.message_url}\n"
                    del possible_message

                    if failed_to_timeout:
                        # moderation_channel.send()
                        await message.channel.send(
                            f"Wasn't able to timeout user {message.author.mention} due to an error of permissions.\nList of possible recent messages:\n{formated_list_possible_recent_messages_from_user}\n{mod_pings}")
                    else:
                        f"User {message.author.mention} has been timeout for {self.config.timeout_hours} hours.\nList of possible recent messages:\n{formated_list_possible_recent_messages_from_user}\n{mod_pings}"

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
        async with self.lock:
            print("start job")
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
                                f"Deleting message {message.id} from user {message.author_id} (server {message.server_id})")
                            author.messages.remove(message)


global_thresholds_seconds = 7
global_count_threshold = 5

if __name__ == '__main__':
    _intents = discord.Intents.default()
    _intents.message_content = True
    _intents.members = True

    token = os.getenv("API_TOKEN")
    client = MyBot(_intents)
    client.run(token)
