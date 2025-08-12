from dataclasses import field

from MessagesClasses import *
import os


@dataclasses.dataclass
class ThresholdConfig:
    # Every when to clean up the internal cache/or also named as how wide is the margin.
    global_thresholds_seconds = None
    # Total number of hits (per used) allowed. Triggers at 4
    global_same_link_threshold = None
    # Allowing a total of 10 links sent per used within 5 seconds. Triggers at 11
    global_total_links_threshold = None

    def __post_init__(self):
        self.global_thresholds_seconds = self.global_thresholds_seconds or int(
            os.getenv("GLOBAL_THRESHOLDS_SECONDS", 3))
        self.global_same_link_threshold = self.global_same_link_threshold or int(
            os.getenv("GLOBAL_SAME_LINK_THRESHOLD", 5))
        self.global_total_links_threshold = self.global_total_links_threshold or int(
            os.getenv("GLOBAL_TOTAL_LINKS_THRESHOLD", 8))

        # print(self.__dict__)


@dataclasses.dataclass
class Config:
    messages_db: MessagesDB
    timeout_hours: int = 5  # On trigger set 5h of timeout
    moderation_roles: list[int] = field(default=list)
    server_id: int | None = None
    threshold_config: ThresholdConfig = None

    # thresholds_seconds: int
    # count_threshold: 5
    def __post_init__(self):
        self.moderation_roles = [int(role_id) for role_id in os.getenv("DISCORD_MODERATION_ROLES", "").split()]
        if len(self.moderation_roles) < 1:
            print("No moderation roles (env DISCORD_MODERATION_ROLES) were specified. If no moderation_roles are set, "
                  "only the server owner will be able interact with this bot.")
        # TODO maybe only check for permissions and forget about moderation roles? That way can be used in multiple
        #  servers

        try:
            self.server_id = int(os.getenv("DISCORD_SERVER_ID"))
        except TypeError as e:
            print("Either the DISCORD_SERVER_ID env value was not an integer or was empty. Exiting")
            raise e

        self.threshold_config = self.threshold_config or ThresholdConfig()

        # print(self.__dict__)
