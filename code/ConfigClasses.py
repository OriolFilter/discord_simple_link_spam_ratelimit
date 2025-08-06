from MessagesClasses import *


@dataclasses.dataclass
class Config:
    messages_db: MessagesDB
    timeout_hours: int
    moderation_roles: list[int]
    server_id: str | None  # Int? TODO
    # thresholds_seconds: int
    # count_threshold: 5
