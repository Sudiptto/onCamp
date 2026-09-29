from jobs.club_discovery.accounts import extract_public_accounts, normalize_account
from jobs.tests.conftest import load_fixture


def test_normalize_account_maps_standard_hiker_fields():
    account = {
        "pk": "12339415936",
        "id": "12339415936",
        "username": "bcc.hunter",
        "full_name": "Burmese Culture Club at Hunter College",
        "profile_pic_url": "https://instagram.example.com/bcc_hunter.jpg",
        "is_private": False,
        "is_verified": False,
    }

    normalized = normalize_account(account)

    assert normalized == {
        "username": "bcc.hunter",
        "user_id": "12339415936",
        "full_name": "Burmese Culture Club at Hunter College",
        "profile_pic_url": "https://instagram.example.com/bcc_hunter.jpg",
        "is_private": False,
    }


def test_normalize_account_supports_fallback_field_names():
    # No "pk", "profile_pic_url", "full_name", or "is_private" keys present.
    account = {
        "id": "70000000001",
        "username": "hunter_altfields_example",
        "name": "Alt Fields Example Club",
        "profile_picture": "https://instagram.example.com/alt_fields_example.jpg",
    }

    normalized = normalize_account(account)

    assert normalized["user_id"] == "70000000001"
    assert normalized["full_name"] == "Alt Fields Example Club"
    assert normalized["profile_pic_url"] == "https://instagram.example.com/alt_fields_example.jpg"
    assert normalized["is_private"] is False


def test_normalize_account_defaults_missing_optional_fields():
    normalized = normalize_account({"pk": "1", "username": "no_name_account"})

    assert normalized["full_name"] == ""
    assert normalized["profile_pic_url"] == ""
    assert normalized["is_private"] is False


def test_extract_public_accounts_filters_private_and_normalizes():
    raw_accounts = load_fixture("raw_following_sample.json")
    expected = load_fixture("following_sample.json")

    result = extract_public_accounts(raw_accounts)

    assert result == expected
    assert all(account["is_private"] is False for account in result)
    # The one private synthetic record must not survive filtering.
    assert "private_person_example" not in {account["username"] for account in result}
