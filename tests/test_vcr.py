import zlib
from unittest.case import TestCase
from seleniumwire.request import Response, Request
from vcr import FilesystemRecorder, PathNamingStrategy


class TestPathNamingStrategy(TestCase):
    def test_filesystem_replay(self):
        name = "hello_world"
        z = zlib.compressobj(-1, zlib.DEFLATED, 31)
        body = z.compress(b"hello world") + z.flush()

        recorder = FilesystemRecorder("vcr")
        recorder.record(name, Response(
            status_code=200,
            reason="OK",
            headers={("Host", "foo.bar"), ("foo", "bar"), ("fuzz", "buzz"), ("Content-Encoding", "gzip")},
            body=body
        ))

        response = recorder.replay(name)

        self.assertEqual(200, response.status_code)
        self.assertEqual("OK", response.reason)
        self.assertEqual(b"hello world", response.body)

    def test_generate_name(self):
        strategy = PathNamingStrategy()
        request = Request(
            method="POST",
            url="https://foo.bar/fuzz/buzz/?foo=bar",
            headers={("foo", "bar"), ("fuzz", "buzz")},
            body=b"foo=bar&fuzz=buzz"
        )

        self.assertEqual("foo.bar_POST_fuzz_buzz_2fb8f_b55d9", strategy.name(request))

    def test_generate_name_with_hash_headers(self):
        strategy = PathNamingStrategy(hash_headers=["foo", "test"])
        request = Request(
            method="POST",
            url="https://foo.bar/fuzz/buzz/?foo=bar",
            headers={("foo", "bar"), ("fuzz", "buzz")},
            body=b"foo=bar&fuzz=buzz"
        )

        self.assertEqual("foo.bar_POST_fuzz_buzz_54dcb_2fb8f_b55d9", strategy.name(request))
