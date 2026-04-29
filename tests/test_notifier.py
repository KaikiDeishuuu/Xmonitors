from xmonitors.models import Status
from xmonitors.notifier import should_notify


def test_out_to_in_notifies():
    assert should_notify(Status.OUT_OF_STOCK, Status.IN_STOCK, False, True)


def test_error_to_error_no_spam():
    assert not should_notify(Status.ERROR, Status.ERROR, True, True)


def test_in_to_in_no_notify():
    assert not should_notify(Status.IN_STOCK, Status.IN_STOCK, True, True)
