import dataclasses
import os


@dataclasses.dataclass
class ThresholdConfig:
    # Every when to clean up the internal cache/or also named as how wide is the margin.
    threshold_seconds = None
    # Total number of hits/links (per user and same link) allowed. Triggers when count is above the limit.
    threshold_same_link_limit = None
    # Total number of total hits/links (per user) allowed. Triggers when count is above the limit.
    threshold_total_links_limit = None

    def __post_init__(self):
        self.threshold_seconds = self.threshold_seconds or int(
            os.getenv("THRESHOLD_SECONDS", 3))
        self.threshold_same_link_limit = self.threshold_same_link_limit or int(
            os.getenv("THRESHOLD_SAME_LINK_LIMIT", 4))
        self.threshold_total_links_limit = self.threshold_total_links_limit or int(
            os.getenv("THRESHOLD_TOTAL_LINKS_LIMIT", 8))
