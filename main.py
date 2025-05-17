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


# Each user will have its own
class MessagesDBServerAuthor:
    messages: [MessageRecord]

    def __init__(self):
        self.messages = []

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
            global thresholds_seconds
            bottom_threshold = top_timestamp_threshold - datetime.timedelta(seconds=thresholds_seconds)

            if top_timestamp_threshold >= message.creation_timestamp >= bottom_threshold:
                message_list.append(message)
        return message_list


class MessagesDBServer:
    authors: {id: MessagesDBServerAuthor}

    def __init__(self):
        self.authors: dict[id: MessagesDBServerAuthor] = dict()

    def add_message(self, message_object: MessageRecord):
        if message_object.author_id not in self.authors.keys():
            self.authors[message_object.author_id] = MessagesDBServerAuthor()
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
    # thresholds_seconds: int
    # count_threshold: 5

class MyBot(discord.Client):
    lock = asyncio.Lock

    def __init__(self, intents: discord.Intents = None):
        intents.message_content = True
        super().__init__(intents=intents)

        self.config = Config(
            messages_db=MessagesDB()
        )

        self.lock = asyncio.Lock()

    # @discord.ext. event
    async def on_ready(self):
        print(f'We have logged in as {client.user}')
        self.messages_cleanup.start()

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            pass  # Ignore bots
        elif not message.guild.id:
            pass  # Ignore messages without guild id
        else:
            extractor = URLExtract()

            urlextract = extractor.find_urls(message.content)
            sanitized_urls = [f"{urlparse(link).netloc}/{urlparse(link).path}" for link in urlextract]
            # sanitized_url
            if len(sanitized_urls) > 0:
                message_object = MessageRecord(
                    id=message.id,
                    author_id=message.author.id,
                    server_id=message.guild.id,
                    creation_timestamp=message.created_at,
                    links=sanitized_urls
                )
                self.config.messages_db.add_message(message_object)

                for url in sanitized_urls:
                    count = self.config.messages_db.count_links_from_author(
                        server_id=message_object.server_id,
                        author_id=message_object.author_id,
                        timestamp=message_object.creation_timestamp,
                        url=url)
                    print(f"Count {count} for URL '{url}'")

            else:
                pass
                # Ignore cases where no links are provided.

                # Check threshold
                # If above the threshold
                # 1. Tiemout  # Prevent
                # 2. Ping admins  # Request confirmation
                # 3. Remove recent messages  # Embed in the admins channel for admins to decide what to do with it?

    # @tasks.loop(seconds=1.0, count=5)
    # async def slow_count(self):
    #     print("hi")
    @tasks.loop(seconds= 5)
    async def messages_cleanup(self):
        async with self.lock:
            print("start job")
            global thresholds_seconds
            job_start_timestamp = datetime.datetime.now(datetime.UTC)
            bottom_threshold = job_start_timestamp - datetime.timedelta(seconds=thresholds_seconds+5) # Adding an extra margin just in case
            for server in self.config.messages_db.servers.values():
                server: MessagesDBServer
                for author in server.authors.values():
                    author: MessagesDBServerAuthor
                    for message in author.messages:
                        message: MessageRecord
                        if message.creation_timestamp < bottom_threshold:
                            print(f"Deleting message {message.id} from user {message.author_id} (serger {message.server_id})")
                            author.messages.remove(message)


thresholds_seconds = 7
count_threshold = 5

if __name__ == '__main__':
    _intents = discord.Intents.default()
    _intents.message_content = True

    token = os.getenv("API_TOKEN")
    client = MyBot(_intents)
    client.run(token)
