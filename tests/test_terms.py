from datetime import date

import pytest

from internbot.terms import (
    OTHER_CYCLE, UNSTATED, classify_posting, classify_term, is_wanted, pretty_term,
    term_for_season_field, term_for_source, upcoming_terms,
)

TODAY = date(2026, 10, 13)
WANTED = upcoming_terms(TODAY)


def test_upcoming_terms_roll_forward_with_the_calendar():
    assert upcoming_terms(TODAY) == {("winter", 2027), ("summer", 2027), ("winter", 2028)}
    # mid-January 2027: winter 2027 has just started, summer 2028 isn't real yet
    assert upcoming_terms(date(2027, 1, 15)) == {("winter", 2027), ("summer", 2027), ("winter", 2028)}
    # by late May the winter term is long over and next summer has opened up
    assert upcoming_terms(date(2027, 5, 20)) == {("summer", 2027), ("winter", 2028), ("summer", 2028)}


@pytest.mark.parametrize("text,expected", [
    ("Software Engineering Intern, Summer 2027", "summer-2027"),
    ("Developer Co-op - Winter 2027", "winter-2027"),
    ("Summer 2027 or Winter 2027 internships", "summer-2027 winter-2027"),
    ("2027 Summer Internship", "summer-2027"),
    ("Stagiaire développeur - Été 2027", "summer-2027"),
    ("Stage en informatique, hiver 2027", "winter-2027"),
    ("Software Intern, Fall 2026", OTHER_CYCLE),
    ("Software Intern, Summer 2026", OTHER_CYCLE),
    ("Software Intern, Spring 2027", OTHER_CYCLE),
    ("Software Intern, Summer 2029", OTHER_CYCLE),
    ("Fall 2026 or Summer 2027", "summer-2027"),
    ("Software Intern", UNSTATED),
    ("Candidates graduating by 2027", UNSTATED),
    ("", UNSTATED),
])
def test_classify_term(text, expected):
    assert classify_term(text, WANTED) == expected


@pytest.mark.parametrize("text,expected", [
    ("Internship starting January 2027", "winter-2027"),
    ("Start date: May 2027", "summer-2027"),
    ("Start date: September 2026", OTHER_CYCLE),
    ("Available to start in May 2027 or September 2027", UNSTATED),  # two start dates: ambiguous
    ("The company was founded in May 2027", UNSTATED),  # a month+year with no start cue
])
def test_start_dates_are_read_only_with_a_start_cue(text, expected):
    assert classify_term(text, WANTED) == expected


def test_title_season_without_a_year():
    assert classify_posting("Software Intern - Summer", "", WANTED) == "summer"
    assert classify_posting("Developer Co-op (Winter)", "", WANTED) == "winter"
    assert classify_posting("Software Intern - Fall", "", WANTED) == OTHER_CYCLE
    assert classify_posting("Spring Boot Developer Intern", "", WANTED) == UNSTATED
    assert classify_posting("Software Intern - Fall", "start date: January 2027", WANTED) == "winter-2027"


def test_wanted_and_pretty():
    assert is_wanted("summer") and is_wanted(UNSTATED) and not is_wanted(OTHER_CYCLE)
    assert pretty_term("summer-2027 winter-2027") == "Summer 2027 · Winter 2027"
    assert pretty_term(UNSTATED) == "" and pretty_term(OTHER_CYCLE) == ""


def test_season_field_and_cycle_scoped_boards():
    assert term_for_season_field("Summer", 2027, WANTED) == "summer-2027"
    assert term_for_season_field("Winter", 2027, WANTED) == "winter-2027"
    assert term_for_season_field("Fall", 2027, WANTED) == OTHER_CYCLE
    assert term_for_source(2027, "SWE Intern", WANTED) == "summer-2027"
    assert term_for_source(2027, "SWE Intern (Fall 2026)", WANTED) == OTHER_CYCLE
    assert term_for_source(2027, "Winter 2027 SWE Co-op", WANTED) == "winter-2027"
    assert term_for_source(None, "SWE Intern", WANTED) == UNSTATED
