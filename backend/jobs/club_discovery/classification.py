from typing import Any


CLUB_KEYWORDS = (
    "club",
    "association",
    "society",
    "union",
    "organization",
    "organisation",
    "council",
    "chapter",
    "student government",
    "student association",
    "student organization",
    "team",
)


def classify_account(account: dict[str, Any], keywords: list[str] | None = None) -> dict[str, Any]:
    """Classify a raw public account without making another API request."""
    account_copy = dict(account)
    configured_keywords = tuple(keyword.lower() for keyword in (keywords or []))
    terms = configured_keywords + CLUB_KEYWORDS
    searchable = " ".join(
        str(account_copy.get(field) or "")
        for field in ("username", "full_name")
    ).lower()
    matched_terms = sorted({term for term in terms if term and term in searchable})
    is_club = bool(matched_terms)

    account_copy["account_type"] = "club" if is_club else "other"
    account_copy["club_match_terms"] = matched_terms
    return account_copy


def classify_clubs(
    accounts: list[dict[str, Any]],
    keywords: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    clubs: list[dict[str, Any]] = []
    other_accounts: list[dict[str, Any]] = []
    for account in accounts:
        classified = classify_account(account, keywords)
        if classified["account_type"] == "club":
            clubs.append(classified)
        else:
            other_accounts.append(classified)
    return clubs, other_accounts
