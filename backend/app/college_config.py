import os

COLLEGE_CONFIGS = {
    "hunter": {
        "college_key": "hunter",
        "college_name": "Hunter College",
        "seed_account": "hunterusg",
    },
    "midwood": {
        "college_key": "midwood",
        "college_name": "Midwood High School",
        "seed_account": "therealmidwoodhs",
    },
}


def get_college_config(college_key: str | None = None):
    key = (college_key or os.getenv("COLLEGE_KEY") or "hunter").lower()
    config = COLLEGE_CONFIGS.get(key)
    if config is None:
        return COLLEGE_CONFIGS["hunter"]
    return config
