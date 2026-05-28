from src.proxy.detector import ResponseDetector
from src.models.enums import ErrorType

def test_success():
    detector = ResponseDetector()
    etype, retry = detector.classify(200, {}, {})
    assert etype == ErrorType.SUCCESS
    assert retry is None

def test_bad_request():
    detector = ResponseDetector()
    etype, retry = detector.classify(400, {}, {})
    assert etype == ErrorType.BAD_REQUEST
    assert retry is None

def test_invalid_key():
    detector = ResponseDetector()
    etype, retry = detector.classify(401, {}, {})
    assert etype == ErrorType.KEY_INVALID
    assert retry is None

def test_rate_limit_generic():
    detector = ResponseDetector()
    # 429, no special headers or body
    etype, retry = detector.classify(429, {}, {})
    assert etype == ErrorType.RATE_LIMITED
    assert retry is None

def test_rate_limit_body_daily():
    detector = ResponseDetector()
    body = {"error": {"message": "Your daily quota has been exceeded"}}
    etype, retry = detector.classify(429, body, {})
    assert etype == ErrorType.DAILY_LIMIT_EXCEEDED
    assert retry is None

def test_rate_limit_header_type():
    detector = ResponseDetector()
    headers = {"X-RateLimit-Type": "daily"}
    etype, retry = detector.classify(429, {}, headers)
    assert etype == ErrorType.DAILY_LIMIT_EXCEEDED
    assert retry is None

def test_rate_limit_long_retry():
    detector = ResponseDetector()
    # 3601 seconds is > 3600
    headers = {"Retry-After": "3601"}
    etype, retry = detector.classify(429, {}, headers)
    assert etype == ErrorType.DAILY_LIMIT_EXCEEDED
    assert retry == 3601

def test_rate_limit_retry_after_header():
    detector = ResponseDetector()
    headers = {"Retry-After": "30"}
    etype, retry = detector.classify(429, {}, headers)
    assert etype == ErrorType.RATE_LIMITED
    assert retry == 30

def test_rate_limit_retry_after_body():
    detector = ResponseDetector()
    body = {"error": {"message": "try again in 45.3s"}}
    etype, retry = detector.classify(429, body, {})
    assert etype == ErrorType.RATE_LIMITED
    assert retry == 46  # 45.3 + 1 = 46

def test_network_exception():
    detector = ResponseDetector()
    class TimeoutException(Exception): pass
    etype, retry = detector.classify(0, {}, {}, exception=TimeoutException("timeout"))
    assert etype == ErrorType.TIMEOUT
    assert retry is None

def test_generic_exception():
    detector = ResponseDetector()
    etype, retry = detector.classify(0, {}, {}, exception=Exception("conn error"))
    assert etype == ErrorType.NETWORK_ERROR
    assert retry is None
