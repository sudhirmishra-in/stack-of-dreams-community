import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from navigator.config import QuotaLimits
from navigator.errors import Conflict, QuotaExceeded, ServiceUnavailable
from navigator.quota.ledger import UsageLedger, next_day_reset, next_month_reset
from navigator.quota.pricing import estimate_usd

NOW = 1_792_000_000.0  # fixed clock


@pytest.fixture
def led(aws):
    clock = {"t": NOW}
    ledger = UsageLedger("usage-t", resource=aws, clock=lambda: clock["t"])
    ledger.clock = clock
    return ledger


L = QuotaLimits()


def test_reserve_and_settle_roundtrip_tracks_tokens_and_spend(led):
    r = led.reserve("u1", "key-00000001", L)
    snap = led.snapshot("u1", L)
    assert (snap.daily_requests, snap.monthly_requests, snap.daily_tokens, snap.app_daily_requests) == (1, 1, L.reserve_tokens_per_request, 1)
    led.settle(r, input_tokens=1200, output_tokens=300, usd=0.0001, response_json='{"x":1}')
    snap = led.snapshot("u1", L)
    assert snap.daily_tokens == 1500  # estimate replaced by actual
    assert led.spend_summary() == {"day": "2026-10-14", "requests": 1, "tokens": 1500, "inputTokens": 1200, "outputTokens": 300, "estimatedUsd": 0.0001}
    assert led.cached_response("u1", "key-00000001") == '{"x":1}'


def test_daily_request_limit_blocks_with_429_details(led):
    lim = QuotaLimits(requests_per_user_day=2)
    for i in range(2):
        led.settle(led.reserve("u1", f"key-0000000{i}", lim), input_tokens=10, output_tokens=10, usd=0)
    with pytest.raises(QuotaExceeded) as e:
        led.reserve("u1", "key-00000009", lim)
    assert e.value.details["reason"] == "daily_requests" and e.value.details["resetsAt"] == next_day_reset(NOW)
    assert int(e.value.headers["Retry-After"]) > 0
    assert led.snapshot("u1", lim).daily_requests == 2  # the failed attempt left no trace (atomic)


def test_token_budget_is_enforced_on_estimates_and_actuals(led):
    lim = QuotaLimits(est_tokens_per_user_day=7000, reserve_tokens_per_request=3000)
    r1 = led.reserve("u1", "key-00000001", lim)
    led.settle(r1, input_tokens=3000, output_tokens=400, usd=0)  # actual 3400
    r2 = led.reserve("u1", "key-00000002", lim)  # 3400 + 3000 <= 7000
    led.settle(r2, input_tokens=3000, output_tokens=400, usd=0)
    with pytest.raises(QuotaExceeded) as e:
        led.reserve("u1", "key-00000003", lim)  # 6800 + 3000 > 7000
    assert e.value.details["reason"] == "daily_tokens"


def test_monthly_and_application_limits(led):
    lim = QuotaLimits(requests_per_user_month=1, requests_per_app_day=5)
    led.settle(led.reserve("u1", "key-00000001", lim), input_tokens=1, output_tokens=1, usd=0)
    with pytest.raises(QuotaExceeded) as e:
        led.reserve("u1", "key-00000002", lim)
    assert e.value.details["reason"] == "monthly_requests" and e.value.details["resetsAt"] == next_month_reset(NOW)
    lim2 = QuotaLimits(requests_per_app_day=3)  # u1 above already used one
    led.settle(led.reserve("a", "key-0000000a", lim2), input_tokens=1, output_tokens=1, usd=0)
    led.settle(led.reserve("b", "key-0000000b", lim2), input_tokens=1, output_tokens=1, usd=0)
    with pytest.raises(QuotaExceeded) as e:
        led.reserve("c", "key-0000000c", lim2)
    assert e.value.details["reason"] == "application_daily"


def test_one_concurrent_request_per_user(led):
    r = led.reserve("u1", "key-00000001", L)
    with pytest.raises(QuotaExceeded) as e:
        led.reserve("u1", "key-00000002", L)
    assert e.value.details["reason"] == "concurrent_request"
    assert led.snapshot("u1", L).daily_requests == 1  # rejected attempt rolled back entirely
    led.settle(r, input_tokens=1, output_tokens=1, usd=0)
    led.reserve("u1", "key-00000003", L)  # slot freed
    led.reserve("u2", "key-00000004", L)  # other users unaffected


def test_stale_slot_expires_so_a_crashed_request_cannot_lock_a_user_out(led):
    led.reserve("u1", "key-00000001", L)  # never settled: simulated crash
    led.clock["t"] += L.request_timeout_seconds + 31
    led.reserve("u1", "key-00000002", L)


def test_configurable_concurrency(led):
    lim = QuotaLimits(max_concurrent_per_user=2)
    led.reserve("u1", "key-00000001", lim)
    led.reserve("u1", "key-00000002", lim)
    with pytest.raises(QuotaExceeded):
        led.reserve("u1", "key-00000003", lim)


def test_idempotency_duplicate_is_rejected_and_replay_is_free(led):
    r = led.reserve("u1", "key-00000001", L)
    with pytest.raises(Conflict):
        led.reserve("u1", "key-00000001", L)  # in progress
    led.settle(r, input_tokens=100, output_tokens=50, usd=0, response_json=json.dumps({"response": "hi"}))
    before = led.snapshot("u1", L)
    with pytest.raises(Conflict):
        led.reserve("u1", "key-00000001", L)  # completed: caller replays the cached answer instead
    assert json.loads(led.cached_response("u1", "key-00000001")) == {"response": "hi"}
    assert led.snapshot("u1", L) == before  # a retry did not charge again
    led.reserve("u2", "key-00000001", L)  # keys are per user


def test_release_refunds_atomically_and_allows_a_safe_retry_with_the_same_key(led):
    r = led.reserve("u1", "key-00000001", L)
    led.release(r)
    s = led.snapshot("u1", L)
    assert (s.daily_requests, s.monthly_requests, s.daily_tokens, s.app_daily_requests) == (0, 0, 0, 0)
    r2 = led.reserve("u1", "key-00000001", L)  # same key: the failed attempt was never charged
    assert led.snapshot("u1", L).daily_requests == 1
    led.settle(r2, input_tokens=10, output_tokens=10, usd=0)
    with pytest.raises(Conflict):
        led.release(r2) if False else led.reserve("u1", "key-00000001", L)  # completed: no double charge


def test_release_cannot_refund_a_settled_request(led):
    r = led.reserve("u1", "key-00000001", L)
    led.settle(r, input_tokens=10, output_tokens=10, usd=0)
    before = led.snapshot("u1", L)
    with pytest.raises(ServiceUnavailable):
        led.release(r)  # the guard (status must still be 'reserved') rolls the whole refund back
    assert led.snapshot("u1", L) == before


def test_event_counters_are_independent_and_bounded(led):
    led.count_event("u1", "routes", 2)
    led.count_event("u1", "routes", 2)
    with pytest.raises(QuotaExceeded) as e:
        led.count_event("u1", "routes", 2)
    assert e.value.details["reason"] == "routes"
    led.count_event("u1", "rejections", 2)  # a different counter


def test_settle_without_counting_the_request_for_classifier_rejections(led):
    r = led.reserve("u1", "key-00000001", L)
    led.settle(r, input_tokens=200, output_tokens=5, usd=0, count_request=False)
    s = led.snapshot("u1", L)
    assert s.daily_requests == 0 and s.daily_tokens == 205  # tokens are charged, the quota request is not


def test_rejection_counter_is_bounded(led):
    lim = QuotaLimits(rejections_per_user_day=2)
    led.count_rejection("u1", lim)
    led.count_rejection("u1", lim)
    with pytest.raises(QuotaExceeded) as e:
        led.count_rejection("u1", lim)
    assert e.value.details["reason"] == "rejections"


def test_counters_reset_on_the_next_day(led):
    lim = QuotaLimits(requests_per_user_day=1)
    led.settle(led.reserve("u1", "key-00000001", lim), input_tokens=1, output_tokens=1, usd=0)
    with pytest.raises(QuotaExceeded):
        led.reserve("u1", "key-00000002", lim)
    led.clock["t"] += 86400
    led.reserve("u1", "key-00000003", lim)


def test_admin_overrides_and_kill_switches(led):
    assert led.effective("u1").limits == L and not led.effective("u1").disabled
    led.set_quota_overrides({"requests_per_user_day": 5, "bogus": 9, "max_query_chars": -1}, "admin-1")
    assert led.effective("u1").limits.requests_per_user_day == 5
    led.set_user_profile("u1", disabled=None, overrides={"requests_per_user_day": 7}, actor="admin-1")
    assert led.effective("u1").limits.requests_per_user_day == 7 and led.effective("u2").limits.requests_per_user_day == 5
    led.set_user_profile("u1", disabled=True, overrides=None, actor="admin-1")
    e = led.effective("u1")
    assert e.disabled and e.limits.requests_per_user_day == 7  # earlier override kept
    led.set_switch(False, "admin-1")
    assert led.effective("u2").assistant_enabled is False


def test_concurrent_reservations_never_exceed_the_limit(led):
    """Many callers race for 3 slots of quota.

    CAVEAT: moto does not isolate TransactWriteItems between threads (real DynamoDB does: transactions are
    serializable). We therefore serialize the emulator's transaction call. This proves that every limit check
    lives INSIDE the single transaction (no read-then-write gap); DynamoDB's isolation itself can only be
    proven by the gated real-AWS smoke test.
    """
    lim = QuotaLimits(requests_per_user_day=3, requests_per_app_day=1000, max_concurrent_per_user=5)
    results = []
    lock = threading.Lock()
    tx_lock = threading.Lock()
    real_tx = led._tx

    def serialized_tx(items):
        with tx_lock:
            return real_tx(items)

    led._tx = serialized_tx

    def attempt(i):
        try:
            led.reserve("u1", f"key-{i:08d}", lim)
            outcome = "ok"
        except QuotaExceeded:
            outcome = "limited"
        with lock:
            results.append(outcome)

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(attempt, range(12)))
    assert results.count("ok") == 3 and results.count("limited") == 9
    assert led.snapshot("u1", lim).daily_requests == 3


def test_fails_closed_when_the_ledger_is_unavailable(aws):
    broken = UsageLedger("does-not-exist", resource=aws)
    with pytest.raises(ServiceUnavailable):
        broken.reserve("u1", "key-00000001", L)
    with pytest.raises(ServiceUnavailable):
        broken.effective("u1")


def test_pricing_is_estimate_only_and_unknown_models_are_not_guessed():
    assert estimate_usd("us.amazon.nova-micro-v1:0", 1000, 1000) == pytest.approx(0.000175)
    assert estimate_usd("some.unknown-model", 1000, 1000) is None
