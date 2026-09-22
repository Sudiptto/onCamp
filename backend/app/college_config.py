import os

COLLEGE_CONFIGS = {
    "hunter": {
        "college_key": "hunter",
        "college_name": "Hunter College",
        "seed_account": "hunterusg",
        "keywords": [
            "club",
            "union",
            "org",
            "society",
            "council",
            "association",
            "chapter",
            "team",
            "student government",
        ],
    },
}


def get_college_config(college_key: str | None = None):
    key = (college_key or os.getenv("COLLEGE_KEY") or "hunter").lower()
    config = COLLEGE_CONFIGS.get(key)
    if config is None:
        return COLLEGE_CONFIGS["hunter"]
    return config
