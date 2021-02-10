import os
import re
import zlib
import brotli
import hashlib
from urllib.parse import urlparse
from seleniumwire.request import Request, Response


def has_header(headers, key: str, value: str = None):
    for (k, v) in headers:
        if k.lower() == key.lower() and (value is None or v.lower() == value.lower()):
            return True
    return False


def is_gzip_encoding(headers) -> bool:
    return has_header(headers, "Content-Encoding", "gzip")


def is_br_encoding(headers) -> bool:
    return has_header(headers, "Content-Encoding", "br")


def psr7_parse_response(message: bytes) -> dict:
    message = message.rstrip(b"\r\n")
    message_parts = re.split(b"\r?\n\r?\n", message, maxsplit=1)

    raw_headers = message_parts[0].decode("utf-8")
    body = message_parts[1] if len(message_parts) > 1 else ""

    raw_headers += "\r\n"
    header_parts = re.split("\r?\n", raw_headers, maxsplit=1)
    [start_line, raw_headers] = header_parts
    matches = re.match("(?:^HTTP\/|^[A-Z]+ \S+ HTTP\/)(\d+(?:\.\d+)?)", start_line)
    if matches and matches[1] == "1.0":
        raw_headers = re.sub(r'(\r?\n[ \t]+)', ' ', raw_headers)

    headers = filter(None, re.split("\r?\n", raw_headers))
    headers = map(lambda header: header.split(":", maxsplit=1), headers)
    headers = [(str(name).strip(), str(value).strip()) for name, value in headers]

    # if is_gzip_encoding(headers):
    #     z = zlib.compressobj(-1, zlib.DEFLATED, 31)
    #     body = z.compress(body) + z.flush()
    # if is_br_encoding(headers):
    #     body = brotli.compress(body)

    return {"start-line": start_line, "headers": headers, "body": body}


def psr7_str(message: Request or Response) -> bytes:
    msg = ""
    if isinstance(message, Request) is True:
        msg = "%s %s HTTP/1.1" % (message.method, message.url)
        if "host" in map(lambda header: str(header[0]).strip().lower(), message.headers):
            msg += "\r\nHost:" + urlparse(message.url).hostname

    if isinstance(message, Response) is True:
        msg = "HTTP/1.1 %s %s" % (message.status_code, message.reason)

    headers = message.headers.items()

    body = message.body
    if is_gzip_encoding(headers):
        body = zlib.decompress(body, 16 + zlib.MAX_WBITS)
    elif is_br_encoding(headers):
        body = brotli.decompress(body)

    headers = filter(lambda header: has_header([header], "Transfer-Encoding", "chunked") is False, headers)
    headers = filter(lambda header: has_header([header], "Content-Encoding") is False, headers)
    # headers = filter(lambda header: has_header([header], "Content-Length") is False, headers)
    headers = sorted(list(headers))

    msg += "".join(["\r\n%s: %s" % (name, value) for name, value in headers])

    return ("%s\r\n\r\n" % msg).encode("utf-8") + body


def generate_hash(value: str) -> str:
    return hashlib.sha1(str(value).encode("utf-8")).hexdigest()[0:5]


class PathNamingStrategy(object):
    def __init__(self, hash_headers: list = None, hash_body_methods: list = None):
        self.hash_headers = [] if hash_headers is None else hash_headers
        self.hash_body_methods = ["PUT", "POST", "PATCH"] if hash_body_methods is None else hash_body_methods

    def name(self, request: Request) -> str:
        uri = urlparse(request.url)
        method = request.method.upper()

        parts = [
            uri.hostname,
            method,
            self.__hash_when_path_too_long(uri.path),
            self.__get_header_hash(request)
        ]

        if request.querystring.strip() != "":
            parts.append(generate_hash(request.querystring.strip()))

        if method in self.hash_body_methods:
            parts.append(generate_hash(request.body.decode("utf-8")))

        return "_".join(list(filter(None, parts)))

    def __get_header_hash(self, request: Request) -> str:
        headers = request.headers
        results = ["%s:%s" % (name, headers.get(name)) for name in self.hash_headers if headers.get(name)]

        return generate_hash(";".join(results)) if len(results) > 0 else ""

    @staticmethod
    def __hash_when_path_too_long(path):
        return path.strip("/").replace("/", "_") if len(path) < 100 else generate_hash(path)


class FilesystemRecorder(object):
    def __init__(self, directory: str):
        if os.path.isdir(directory) is False:
            os.makedirs(directory)
        self.directory = os.path.realpath(directory) + os.sep

    def record(self, name: str, response: Response) -> None:
        filename = "%s%s.txt" % (self.directory, name)
        with open(filename, "wb+") as stream:
            stream.write(psr7_str(response))

    def replay(self, name: str) -> Response or None:
        filename = "%s%s.txt" % (self.directory, name)

        if os.path.exists(filename) is False:
            return None

        with open(filename, "rb+") as fp:
            message = fp.read()

        data = psr7_parse_response(message)
        # print(re.match("^HTTP\/.* [0-9]{3}( .*|$)", data['start-line'])

        parts = re.split(" ", data["start-line"], maxsplit=2)

        return Response(
            status_code=int(parts[1]),
            reason=parts[2],
            headers=data["headers"],
            body=data["body"]
        )


class VCR:
    def __init__(self, naming_strategy: PathNamingStrategy, recorder: FilesystemRecorder):
        self.naming_strategy = naming_strategy
        self.recorder = recorder

    def replay(self, request: Request) -> None:
        name = self.naming_strategy.name(request)
        response = self.recorder.replay(name)
        if response is not None:
            headers = response.headers.items()

            request.create_response(
                status_code=200,
                headers=headers,
                body=response.body,
            )

    def record(self, request: Request, response: Response) -> None:
        name = self.naming_strategy.name(request)
        self.recorder.record(name, response)
