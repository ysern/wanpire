"""The broker: leases, the queue, their TTLs. A fake clock; nothing sleeps."""

import pytest

from wanpire.broker import Broker, LeaseEnded, NotHolder, UnknownTicket


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def cleared():
    return []


@pytest.fixture
def broker(clock, cleared):
    return Broker(clock=clock, on_clear=lambda: cleared.append(clock()))


def test_the_first_asks_and_holds(broker):
    a = broker.request("A", "soak")
    assert a.holds and a.position == 0
    assert broker.status()["holder"]["who"] == "A"


def test_two_more_queue_in_order(broker):
    broker.request("A", "x")
    b = broker.request("B", "y")
    c = broker.request("C", "z")
    assert (b.holds, b.position) == (False, 1)
    assert (c.holds, c.position) == (False, 2)
    assert [q["who"] for q in broker.status()["queue"]] == ["B", "C"]


def test_asking_again_with_a_ticket_polls(broker):
    a = broker.request("A", "x")
    again = broker.poll(a.ticket)
    assert again.holds and again.ticket == a.ticket
    b = broker.request("B", "y")
    assert broker.poll(b.ticket).position == 1


def test_a_crashed_client_leaves_the_queue(broker, clock):
    broker.request("A", "x")
    b = broker.request("B", "y")
    c = broker.request("C", "z")
    for _ in range(3):
        clock.advance(20)
        broker.poll(c.ticket)
    clock.advance(1)  # B last polled 61 s ago
    assert broker.poll(c.ticket).position == 1
    with pytest.raises(UnknownTicket):
        broker.poll(b.ticket)


def test_the_holder_releases_and_the_next_holds(broker, cleared):
    a = broker.request("A", "x")
    b = broker.request("B", "y")
    broker.release(a.ticket)
    assert len(cleared) == 1
    assert broker.poll(b.ticket).holds


def test_the_holder_goes_silent(broker, clock, cleared):
    a = broker.request("A", "x")
    b = broker.request("B", "y")
    for _ in range(6):
        clock.advance(20)
        broker.poll(b.ticket)
    clock.advance(1)  # A's last call was 121 s ago
    assert broker.poll(b.ticket).holds
    assert len(cleared) == 1
    with pytest.raises(LeaseEnded, match="expired"):
        broker.poll(a.ticket)


def test_the_next_holders_ttl_starts_when_it_is_granted(broker, clock):
    a = broker.request("A", "x")
    b = broker.request("B", "y")
    clock.advance(50)
    broker.poll(b.ticket)
    broker.release(a.ticket)
    clock.advance(119)
    assert broker.poll(b.ticket).holds  # granted 119 s ago, still alive


def test_nobody_waiting(broker, cleared):
    a = broker.request("A", "x")
    broker.release(a.ticket)
    assert cleared and broker.status()["holder"] is None


def test_a_change_without_the_lease_names_the_holder(broker):
    broker.request("A", "nightly soak")
    b = broker.request("B", "y")
    with pytest.raises(NotHolder, match="A.*nightly soak"):
        broker.require(b.ticket)


def test_a_change_renews_the_lease(broker, clock):
    a = broker.request("A", "x")
    for _ in range(5):
        clock.advance(100)
        broker.require(a.ticket)
    assert broker.status()["holder"]["who"] == "A"


def test_the_status_is_open(broker, clock):
    broker.request("A", "nightly soak")
    clock.advance(30)
    broker.request("B", "y")
    s = broker.status()
    assert s["holder"]["who"] == "A" and s["holder"]["purpose"] == "nightly soak"
    assert s["holder"]["held_s"] == 30
    assert s["holder"]["expires_in_s"] == 90
    assert s["queue"][0]["who"] == "B" and s["queue"][0]["expires_in_s"] == 60
    assert "ticket" not in s["holder"]  # nobody reads a ticket out of the status


def test_ended_by_hand(broker, cleared):
    a = broker.request("A", "x")
    b = broker.request("B", "y")
    broker.end_lease("the lab needs the line")
    assert cleared
    assert broker.poll(b.ticket).holds
    with pytest.raises(LeaseEnded, match="the lab needs the line"):
        broker.poll(a.ticket)
    with pytest.raises(UnknownTicket):  # told once
        broker.poll(a.ticket)


def test_a_failing_clear_still_passes_the_lease_on(clock):
    def boom():
        raise RuntimeError("tc failed")
    br = Broker(clock=clock, on_clear=boom)
    a = br.request("A", "x")
    b = br.request("B", "y")
    br.release(a.ticket)
    assert br.poll(b.ticket).holds
    assert "tc failed" in br.status()["last_clear_error"]


def test_ttls_are_configuration(clock):
    br = Broker(clock=clock, lease_ttl_s=10, queue_ttl_s=5)
    a = br.request("A", "x")
    b = br.request("B", "y")
    clock.advance(6)
    with pytest.raises(UnknownTicket):
        br.poll(b.ticket)
    clock.advance(5)
    with pytest.raises(LeaseEnded):
        br.poll(a.ticket)


def test_releasing_a_queued_request_leaves_the_queue(broker):
    broker.request("A", "x")
    b = broker.request("B", "y")
    c = broker.request("C", "z")
    broker.release(b.ticket)
    assert broker.poll(c.ticket).position == 1


def test_tickets_differ(broker):
    assert broker.request("A", "x").ticket != broker.request("A", "x").ticket
