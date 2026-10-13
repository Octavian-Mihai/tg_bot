import pytest

from internbot import places


@pytest.mark.parametrize("text", [
    "Montréal, QC", "MONTREAL", "Dorval, Quebec", "Brossard", "Laval, QC", "Remote - Canada", "Canada",
    "Toronto ; Montreal", "Quebec City, Québec",
])
def test_in_area(text):
    assert places.in_area(text)


@pytest.mark.parametrize("text", [
    "Toronto, Ontario", "Remote - Canada - ON", "Vancouver, BC", "Lisbon, Portugal", "Utrecht, nl",
    "Laval, France", "Kirkland, WA", "San Francisco, CA", "", None,
])
def test_out_of_area(text):
    assert not places.in_area(text)


def test_remote_canada_can_be_switched_off():
    places.configure(["montreal"], remote_canada=False)
    assert not places.in_area("Remote - Canada") and places.in_area("Montréal")
