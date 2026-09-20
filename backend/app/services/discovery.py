import os


class DiscoveryService:
    """Configuration-first service for discovering clubs from a single seed account.

    This starts with Hunter as the default campus and is designed to be generalized
    to other colleges by swapping the seed account and college metadata.
    """

    def __init__(self, seed_account: str | None = None, college_name: str = "Hunter"):
        self.seed_account = seed_account or os.getenv("SEED_ACCOUNT", "hunterusg")
        self.college_name = college_name

    def get_seed_context(self):
        return {
            "college": self.college_name,
            "seed_account": self.seed_account,
            "status": "configured",
            "pipeline": "instagram-discovery",
        }

    def build_discovery_plan(self):
        return {
            "target": self.seed_account,
            "steps": [
                "fetch public account metadata",
                "map follow graph from seed account",
                "filter to campus-affiliated clubs",
                "store active club records",
                "queue daily post scans",
            ],
        }
