import dataclasses
import datetime
from ConfigClasses import ThresholdConfig


@dataclasses.dataclass
class MessageRecord:
    id: int
    author_id: int
    server_id: int
    creation_timestamp: datetime.datetime
    urls: list[str]
    message_url: str

    # def __eq__(self, other):
    #     print(f"comparing {self.__class__} and {other.__class__}")
    #     if not isinstance(other, MessageRecord):
    #         return False
    #     return (
    #             self.id == other.id and
    #             self.author_id == other.author_id and
    #             self.server_id == other.server_id and
    #             # self.urls == other.urls and
    #             self.message_url == other.message_url and
    #             self.creation_timestamp == other.creation_timestamp
    #             )
    #
    def __hash__(self):
        # print(f"hashing {self.__class__}")
        return hash((self.id,
                     self.author_id,
                     self.server_id,
                     # self.urls,
                     self.message_url,
                     self.creation_timestamp
                     ))


# Each user will have its own
class MessagesDBServerAuthor:
    messages: [MessageRecord]
    id: int
    timed_out: bool
    timed_out_timestamp: datetime.datetime | None
    config: ThresholdConfig

    def __init__(self, id: int, config: ThresholdConfig):
        self.messages = []
        self.id = int(id)
        self.timed_out = False
        self.config = config

    def add_message(self, message_object: MessageRecord):
        self.messages.append(message_object)
        # print(f"Total messages from user {message_object.author_id} ({len(self.messages)})")

    def count_links_from_author(self, timestamp: datetime.datetime, url: str) -> int:
        count = 0
        for message in self.get_messages_within_threshold(timestamp):
            if url in message.urls:
                count += 1
        return count

    def count_total_sent_links_from_author(self, timestamp: datetime.datetime) -> int:
        return sum([len(message.urls) for message in self.get_messages_within_threshold(timestamp)])

    def get_messages_within_threshold(self, top_timestamp_threshold: datetime.datetime) -> list[MessageRecord]:
        message_list = []
        for message in self.messages:
            message: MessageRecord
            bottom_threshold = top_timestamp_threshold - datetime.timedelta(
                seconds=self.config.global_thresholds_seconds)

            if top_timestamp_threshold >= message.creation_timestamp >= bottom_threshold:
                message_list.append(message)
        return message_list

    def get_uniq_urls(self) -> list[str]:

        url_list = []
        for message in self.messages:
            message: MessageRecord
            url_list += message.urls
        url_list.sort()

        return list(dict.fromkeys(url_list))

    def set_cache_timeout(self):
        self.timed_out = True
        self.timed_out_timestamp = datetime.datetime.now(datetime.UTC)

    def clear_cache_timout(self):
        self.timed_out = False
        self.timed_out_timestamp = None
        print(f"Clear cache: User {self.id} no longer in the cached timeout")


class MessagesDBServer:
    authors: {id: MessagesDBServerAuthor}
    config: ThresholdConfig

    def __init__(self, config: ThresholdConfig):
        self.authors: dict[id: MessagesDBServerAuthor] = dict()
        self.config = config

    def add_message(self, message_object: MessageRecord):
        if message_object.author_id not in self.authors.keys():
            self.authors[message_object.author_id] = MessagesDBServerAuthor(id=message_object.author_id,
                                                                            config=self.config)
        self.authors[message_object.author_id].add_message(message_object)

    def count_links_from_author(self, author_id: int, timestamp: datetime.datetime, url: str) -> int:
        if author_id not in self.authors.keys():
            return 0
        else:
            return self.authors[author_id].count_links_from_author(
                timestamp=timestamp,
                url=url
            )

    def count_total_sent_links_from_author(self, author_id: int, timestamp: datetime.datetime) -> int:
        if author_id not in self.authors.keys():
            return 0
        else:
            return self.authors[author_id].count_total_sent_links_from_author(
                timestamp=timestamp
            )


class MessagesDB:
    servers: dict[id: MessagesDBServer]
    config: ThresholdConfig

    def __init__(self, config: ThresholdConfig):
        self.servers: dict[id: MessagesDBServer] = dict()
        self.config = config

    def add_message(self, message_object: MessageRecord):
        if message_object.server_id not in self.servers.keys():
            self.servers[message_object.server_id] = MessagesDBServer(config=self.config)
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

    def count_total_sent_links_from_author(self, server_id: int, author_id: int, timestamp: datetime.datetime) -> int:
        if server_id not in self.servers.keys():
            return 0
        else:
            return self.servers[server_id].count_total_sent_links_from_author(
                author_id=author_id,
                timestamp=timestamp
            )
