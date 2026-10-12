"""佇列語意：併發 claim 只發一次、done 冪等、失敗 3 次標 error、租約逾時可重領。"""
from concurrent.futures import ThreadPoolExecutor

import psycopg


def test_concurrent_claim_hands_out_each_job_once(store):
    store.enqueue([(f"https://www.threads.com/@a/post/{i}", "threads") for i in range(5)], "U1")
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(lambda _: store.claim(), range(10)))
    claimed = [j.id for j in results if j is not None]
    assert sorted(claimed) == [1, 2, 3, 4, 5]
    assert len(claimed) == len(set(claimed))


def test_claim_fifo_and_empty(store):
    store.enqueue([("https://a", "article"), ("https://b", "article")], "U1")
    assert store.claim().url == "https://a"
    assert store.claim().url == "https://b"
    assert store.claim() is None


def test_done_is_idempotent(store):
    (job,) = store.enqueue([("https://a", "article")], "U1")
    store.claim()
    first, changed1 = store.finish(job.id, True, {"title": "T"}, None)
    second, changed2 = store.finish(job.id, True, {"title": "OTHER"}, None)
    assert (first.status, changed1) == ("done", True)
    assert (second.status, changed2) == ("done", False)
    assert second.result_json == {"title": "T"}


def test_failure_requeues_until_max_attempts(store):
    (job,) = store.enqueue([("https://a", "article")], "U1")
    for attempt in (1, 2):
        assert store.claim().attempts == attempt
        failed, _ = store.finish(job.id, False, None, "boom")
        assert failed.status == "queued"
    assert store.claim().attempts == 3
    final, _ = store.finish(job.id, False, None, "boom")
    assert final.status == "error"
    assert final.result_json == {"error": "boom"}
    assert store.claim() is None


def test_finish_unknown_job(store):
    assert store.finish(999, True, {}, None) == (None, False)


def test_stale_working_is_reclaimed_then_expires(store, database_url):
    (job,) = store.enqueue([("https://a", "article")], "U1")
    store.claim()
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("UPDATE scraper_jobs SET updated_at = now() - interval '2 hours'")
    again = store.claim()
    assert (again.id, again.attempts) == (job.id, 2)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("UPDATE scraper_jobs SET attempts = 3, updated_at = now() - interval '2 hours'")
    assert store.claim() is None
    _, _ = store.finish(job.id, True, {}, None)  # 已 error，不可被改回 done
    with psycopg.connect(database_url) as conn:
        assert conn.execute("SELECT status FROM scraper_jobs").fetchone()[0] == "error"


def test_rls_enabled(store, database_url):
    with psycopg.connect(database_url) as conn:
        assert conn.execute(
            "SELECT relrowsecurity FROM pg_class WHERE relname = 'scraper_jobs'").fetchone()[0] is True
