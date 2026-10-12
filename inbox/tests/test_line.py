import base64
import hashlib
import hmac

from app.line import classify, extract_links, verify_signature


def _sign(secret: str, body: bytes) -> str:
    return base64.b64encode(hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()


def test_verify_signature_accepts_valid():
    body = b'{"events":[]}'
    assert verify_signature("s3cret", body, _sign("s3cret", body))


def test_verify_signature_rejects_tampered_or_missing():
    body = b'{"events":[]}'
    sig = _sign("s3cret", body)
    assert not verify_signature("s3cret", body + b" ", sig)
    assert not verify_signature("other", body, sig)
    assert not verify_signature("s3cret", body, "")


def test_classify():
    assert classify("https://www.threads.com/@a/post/X") == "threads"
    assert classify("https://www.threads.net/@a/post/X") == "threads"
    assert classify("https://instagram.com/p/X/") == "instagram"
    assert classify("https://github.com/psf/requests") == "github"
    assert classify("https://www.bnext.com.tw/article/1") == "article"


def test_extract_links_dedup_and_trailing_punct():
    text = "看這個 https://www.threads.com/@a/post/X。還有 https://github.com/a/b, 跟 https://www.threads.com/@a/post/X"
    assert extract_links(text) == [
        ("https://www.threads.com/@a/post/X", "threads"),
        ("https://github.com/a/b", "github"),
    ]


def test_extract_links_none():
    assert extract_links("哈囉") == []
