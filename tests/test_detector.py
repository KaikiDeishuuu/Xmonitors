from xmonitors.detector import detect_status
from xmonitors.models import Status


def test_positive_keyword_in_stock():
    result = detect_status("You can Order Now", ["Order Now"], ["Sold Out"], ["Access Denied"])
    assert result.status == Status.IN_STOCK


def test_negative_keyword_out_of_stock():
    result = detect_status("Currently Sold Out", ["Order Now"], ["Sold Out"], ["Access Denied"])
    assert result.status == Status.OUT_OF_STOCK


def test_blocked_keyword_blocked():
    result = detect_status("Just a moment...", ["Order Now"], ["Sold Out"], ["Just a moment"])
    assert result.status == Status.BLOCKED


def test_no_match_unknown():
    result = detect_status("No markers", ["Order Now"], ["Sold Out"], ["Access Denied"])
    assert result.status == Status.UNKNOWN


def test_precedence_blocked_over_positive():
    result = detect_status("Order Now but Access Denied", ["Order Now"], ["Sold Out"], ["Access Denied"])
    assert result.status == Status.BLOCKED
