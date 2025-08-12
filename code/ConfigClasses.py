import dataclasses
from dataclasses import field

from MessagesClasses import MessagesDB
import os
from ThresholdConfigClass import ThresholdConfig

@dataclasses.dataclass
class Config:
    messages_db: MessagesDB = field(default=None)
    timeout_hours: int = 5  # On trigger set 5h of timeout
    moderation_roles: list[int] = field(default=list)
    server_id: int | None = None
    threshold_config: ThresholdConfig = None

    def __post_init__(self):
        self.moderation_roles = [int(role_id) for role_id in os.getenv("DISCORD_MODERATION_ROLES", "").split()]
        if len(self.moderation_roles) < 1:
            print("No moderation roles (env DISCORD_MODERATION_ROLES) were specified. If no moderation_roles are set, "
                  "only the server owner will be able interact with this bot.")
        # TODO maybe only check for permissions and forget about moderation roles? That way can be used in multiple
        #  servers, still might be important to limit to "which servers" it operates.

        try:
            self.server_id = int(os.getenv("DISCORD_SERVER_ID"))
        except TypeError as e:
            print("Either the DISCORD_SERVER_ID env value was not an integer or was empty. Exiting")
            raise e

        self.threshold_config = self.threshold_config or ThresholdConfig()

        self.messages_db = MessagesDB(config=self.threshold_config)

        # print(self.__dict__)
