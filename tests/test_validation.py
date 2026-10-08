import pytest

from openiban.validation import validate_german_iban
from tests.conftest import iban_for


@pytest.mark.parametrize(
    "raw",
    [
        "DE58123456780123456789",
        "de58 1234 5678 0123 4567 89",
        "\tDE58\n123456780123456789 ",
        "DE58\u00a0123456780123456789",
    ],
)
def test_normalization_and_checksum(raw):
    result = validate_german_iban(raw)
    assert result.normalized == "DE58123456780123456789"
    assert result.iban_valid is True


@pytest.mark.parametrize(
    "raw, reason",
    [
        ("DE59123456780123456789", "invalid_checksum"),
        ("DE58-123456780123456789", "invalid_format"),
        ("DE5812345678A0123456789", "invalid_format"),
        ("DE5812345678012345678", "invalid_format"),
        ("DE581234567801234567890", "invalid_format"),
        ("DE58１２３４５６７８０１２３４５６７８９", "invalid_characters"),
        ("DE5812345678012345678ß", "invalid_characters"),
        ("", "invalid_format"),
        ("  ", "invalid_format"),
    ],
)
def test_invalid_inputs_are_not_repaired(raw, reason):
    result = validate_german_iban(raw)
    assert result.iban_valid is False
    assert result.reason == reason


def test_unsupported_is_not_reported_as_invalid():
    result = validate_german_iban("GB82WEST12345698765432")
    assert result.reason == "unsupported_country"
    assert result.iban_valid is None
    assert result.checksum_valid is None
    assert "WEST" in result.normalized


def test_mod97_alias_of_noncanonical_check_digits_is_rejected():
    # A check digit of 00 can produce remainder 1, like 97. Reject 00/01/99.
    for account in range(1000):
        iban = iban_for(account=f"{account:010d}")
        if iban[2:4] == "97":
            alias = "DE00" + iban[4:]
            assert int(alias[4:] + "131400") % 97 == 1
            assert validate_german_iban(alias).iban_valid is False
            break
    else:
        pytest.fail("No test vector found")
