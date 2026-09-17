"""Mission 17 U6: self-hosted ntfy, `[notify] ntfy_token` (DESIGN §33, §11, §13, §24, §26).

§33: "`[notify] ntfy_url` and `[notify] ntfy_token` (sent as a bearer on publish
and subscribe); the phone app subscribes with the same token." Every ntfy here is
a stand-in whose topics require the token, the way a server with
`auth-default-access: deny-all` answers: `httpx.MockTransport` for publish and the
long polls, and a stdlib HTTP server on 127.0.0.1 for a kit attachment (the fetch
has no transport seam of its own). No real ntfy server is run.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import threading
import time
from collections.abc import AsyncIterator, Iterator
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import httpx
import pytest

from conftest import strip_paths
from hands import phone as phone_mod
from hands import who
from hands.cli import main
from hands.config import ConfigError, load_config
from hands.daemon import Daemon
from hands.notify import Notifier, http_post, http_stream
from hands.phone import KIT_TITLE, STATUS_TITLE
from hands.spool import Spool
from harness import PROJECT, TIMEOUT, config_body, poll, write_project

NTFY = "https://ntfy.tailnet.example"
TOKEN = "tk_U6selfhostedBearer0123456789ab"
BEARER = f"Bearer {TOKEN}"
EVENTS_TOPIC = "hands-events-u6"
CMD_TOPIC = "hands-cmd-u6"
WHO_TOPIC = "hands-who-u6"
WHO_CMD_TOPIC = "hands-who-cmd-u6"
SECRET = "U6-cmd-secret-0123456789abcdef"


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / "work"
    d.mkdir(exist_ok=True)
    return d


def notify_table(*, token: str | None, url: str = NTFY) -> str:
    lines = [
        "[notify]",
        f'ntfy_url = "{url}"',
        f'ntfy_topic = "{EVENTS_TOPIC}"',
        f'cmd_topic = "{CMD_TOPIC}"',
        f'cmd_secret = "{SECRET}"',
        f'who_topic = "{WHO_TOPIC}"',
        f'who_cmd_topic = "{WHO_CMD_TOPIC}"',
    ]
    if token is not None:
        lines.append(f"ntfy_token = {json.dumps(token)}")
    return "\n".join(lines) + "\n"


def write(
    tmp_home: Path, workdir: Path, *, token: str | None = TOKEN, url: str = NTFY, more: str = ""
) -> str:
    extra = notify_table(token=token, url=url) + more
    return write_project(tmp_home, config_body(tmp_home, workdir, extra=extra))


class DenyAll:
    """An ntfy whose every topic requires the token: 401 without the bearer.

    `lines` is what a GET of a `/json` stream answers; a POST is a publish.
    """

    def __init__(self, lines: list[str] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.lines = lines or []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.headers.get("Authorization") != BEARER:
            return httpx.Response(401, json={"code": 40101, "http": 401, "error": "unauthorized"})
        if request.method == "GET":
            return httpx.Response(200, content=("\n".join(self.lines) + "\n").encode())
        return httpx.Response(200, json={"id": "published"})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def auth(self) -> list[str | None]:
        return [request.headers.get("Authorization") for request in self.requests]


def assert_no_token(*texts: str) -> None:
    for text in texts:
        assert TOKEN not in strip_paths(text)


# ------------------------------------------------------------------- config


def test_the_token_loads_and_stays_out_of_the_configs_repr(
    tmp_home: Path, workdir: Path
) -> None:
    config = load_config(write(tmp_home, workdir))
    assert config.notify.ntfy_token == TOKEN
    assert_no_token(repr(config), repr(config.notify))


def test_without_the_key_there_is_no_token(tmp_home: Path, workdir: Path) -> None:
    assert load_config(write(tmp_home, workdir, token=None)).notify.ntfy_token is None


@pytest.mark.parametrize(
    "value",
    [
        '""',
        '"   "',
        '"Zq9secret inner"',
        '"Zq9secret\\ninner"',
        '"Zq9secret\\tinner"',
        '"Zq9secrét"',
        "90210",
        '["Zq9secret"]',
    ],
    ids=["empty", "blanks", "space", "newline", "tab", "non_ascii", "integer", "list"],
)
def test_a_token_that_cannot_be_a_bearer_is_refused_naming_the_key(
    tmp_home: Path, workdir: Path, value: str
) -> None:
    extra = notify_table(token=None) + f"ntfy_token = {value}\n"
    write_project(tmp_home, config_body(tmp_home, workdir, extra=extra))
    with pytest.raises(ConfigError) as exc:
        load_config(PROJECT)
    message = str(exc.value)
    assert "[notify] ntfy_token" in strip_paths(message)
    assert "Zq9secr" not in strip_paths(message)
    assert "90210" not in strip_paths(message)


# ---------------------------------------------------------------- transport


def test_http_post_sends_the_bearer_only_when_given_one() -> None:
    ntfy = DenyAll()

    async def body() -> tuple[int, int]:
        url = f"{NTFY}/{EVENTS_TOPIC}"
        with_token = await http_post(
            url, title="t", message="m", token=TOKEN, transport=ntfy.transport
        )
        without = await http_post(url, title="t", message="m", transport=ntfy.transport)
        return with_token, without

    assert asyncio.run(body()) == (200, 401)
    assert ntfy.auth() == [BEARER, None]


def test_http_stream_sends_the_bearer_only_when_given_one() -> None:
    ntfy = DenyAll([json.dumps({"event": "open"})])
    url = f"{NTFY}/{CMD_TOPIC}/json?since=1"

    async def read(**kwargs: Any) -> list[str]:
        return [line async for line in http_stream(url, transport=ntfy.transport, **kwargs)]

    assert [json.loads(line)["event"] for line in asyncio.run(read(token=TOKEN))] == ["open"]
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(read())
    assert ntfy.auth() == [BEARER, None]


# ------------------------------------------------------ §11's notifications


@pytest.mark.parametrize("token", [TOKEN, None], ids=["token", "no_token"])
def test_a_notification_is_accepted_with_the_token_and_is_a_failed_publish_without(
    tmp_home: Path, workdir: Path, token: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    config = load_config(write(tmp_home, workdir, token=token))
    ntfy = DenyAll()
    spool = Spool(config.spool_root)
    note = Notifier(config, spool, post=partial(http_post, transport=ntfy.transport))

    async def body() -> None:
        note.notify("hands: the pipeline stopped", {"reason": "blockers"})
        await note.drain()

    asyncio.run(body())
    assert [request.url.path for request in ntfy.requests] == [f"/{EVENTS_TOPIC}"]
    events = spool.events()
    if token is not None:
        assert ntfy.auth() == [BEARER]
        assert events == []
    else:
        assert ntfy.auth() == [None]
        assert [event.kind for event in events] == ["notify"]
        assert events[0].payload["delivered"] is False
        assert "ntfy answered 401" in strip_paths(events[0].payload["error"])
    stored = [path.read_text() for path in config.spool_root.rglob("*") if path.is_file()]
    assert_no_token(caplog.text, *stored)


# ----------------------------------------------------------- notify --test


def run_cli(project: str, *argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = main(["--project", project, *argv], stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


def test_notify_test_sends_the_token_and_never_prints_it(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    project = write(tmp_home, workdir)
    ntfy = DenyAll()
    monkeypatch.setattr("hands.notify.http_post", partial(http_post, transport=ntfy.transport))

    code, out, err = run_cli(project, "notify", "--test", "over the tunnel")
    assert code == 0, err
    assert "ntfy 200" in strip_paths(out)
    code, out_json, err_json = run_cli(project, "--json", "notify", "--test", "again")
    assert code == 0, err_json
    assert json.loads(out_json)["delivered"] is True

    assert ntfy.auth() == [BEARER, BEARER]
    assert_no_token(out, err, out_json, err_json, caplog.text)


def test_notify_test_without_the_token_prints_the_401_and_exits_1(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = write(tmp_home, workdir, token=None)
    ntfy = DenyAll()
    monkeypatch.setattr("hands.notify.http_post", partial(http_post, transport=ntfy.transport))

    code, out, err = run_cli(project, "notify", "--test", "over the tunnel")
    assert code == 1, err
    assert "ntfy 401" in strip_paths(out)
    assert ntfy.auth() == [None]


# ---------------------------------------------------- the command channel


def stream_line(text: str, **fields: Any) -> str:
    return json.dumps(
        {
            "id": f"u6-{time.monotonic_ns()}",
            "time": int(time.time()) + 5,
            "event": "message",
            "topic": CMD_TOPIC,
            "message": text,
            **fields,
        }
    )


async def no_sleep(seconds: float) -> None:
    await asyncio.sleep(0)


async def parked(seconds: float) -> None:
    """The channel's reconnect backoff, parked: one connection is the whole test."""
    await asyncio.sleep(3600)


@pytest.mark.parametrize("token", [TOKEN, None], ids=["token", "no_token"])
def test_the_command_channel_subscribes_with_the_bearer_and_takes_a_command(
    tmp_home: Path, workdir: Path, token: str | None, caplog: pytest.LogCaptureFixture
) -> None:
    """With the token the long poll is authorized and `status` is answered, through
    the real `http_stream` and `http_post`; without it ntfy's 401 is no command."""
    caplog.set_level(logging.DEBUG)
    project = write(tmp_home, workdir, token=token)
    ntfy = DenyAll([json.dumps({"event": "open"}), stream_line(f"status {SECRET}")])
    backoffs: list[float] = []

    async def backoff(seconds: float) -> None:
        backoffs.append(seconds)
        await parked(seconds)

    async def scenario() -> None:
        daemon = Daemon(load_config(project))
        daemon.notifier.post = partial(http_post, transport=ntfy.transport)
        assert daemon.phone is not None
        daemon.phone.stream = partial(http_stream, transport=ntfy.transport)
        daemon.phone.sleep = backoff
        await daemon.start()
        try:

            async def settled() -> bool:
                await daemon.notifier.drain()
                return bool(backoffs)

            await asyncio.wait_for(poll(settled, "the first connection to end"), TIMEOUT)
            await daemon.notifier.drain()
            if token is not None:
                assert daemon.phone.handled == 1
            else:
                assert daemon.phone.handled == 0
        finally:
            await daemon.stop()

    asyncio.run(scenario())
    gets = [request for request in ntfy.requests if request.method == "GET"]
    assert [request.url.path for request in gets] == [f"/{CMD_TOPIC}/json"]
    assert gets[0].headers.get("Authorization") == (BEARER if token else None)
    answers = [
        request
        for request in ntfy.requests
        if request.method == "POST" and request.headers.get("Title") == STATUS_TITLE
    ]
    if token is not None:
        assert len(answers) == 1
        assert answers[0].url.path == f"/{EVENTS_TOPIC}"
        assert set(ntfy.auth()) == {BEARER}  # every publish and the poll
    else:
        assert answers == []
        assert set(ntfy.auth()) == {None}
    assert_no_token(caplog.text)


# ------------------------------------------------------ a kit attachment


class LocalNtfy:
    """An attachment host on 127.0.0.1 that records the Authorization of each GET.

    With `require` set, a GET without the bearer is a 401, as a deny-all ntfy
    answers it.
    """

    def __init__(self, *, require: bool) -> None:
        self.files: dict[str, bytes] = {}
        self.auth: list[str | None] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - http.server's name
                seen = self.headers.get("Authorization")
                owner.auth.append(seen)
                body = owner.files.get(self.path)
                status = 401 if require and seen != BEARER else 200 if body else 404
                self.send_response(status)
                payload = body if status == 200 and body is not None else b""
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"


@pytest.fixture
def hosts() -> Iterator[tuple[LocalNtfy, LocalNtfy]]:
    """The self-hosted ntfy (requires the token) and a foreign host (does not)."""
    servers = (LocalNtfy(require=True), LocalNtfy(require=False))
    for server in servers:
        server.thread.start()
    try:
        yield servers
    finally:
        for server in servers:
            server.httpd.shutdown()
            server.httpd.server_close()


#: An empty zip archive: what is moved is bytes, and no apply is filed for it.
ZIP = b"PK\x05\x06" + bytes(18)


def test_a_kit_on_the_ntfy_server_is_fetched_with_the_bearer_and_a_foreign_one_without(
    tmp_home: Path,
    workdir: Path,
    hosts: tuple[LocalNtfy, LocalNtfy],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The token goes only to `ntfy_url`'s own origin: an attachment URL on another
    host is fetched without it, so the token never leaves for a host it is not for."""
    caplog.set_level(logging.DEBUG)
    ours, foreign = hosts
    downloads = tmp_home / "Downloads"
    downloads.mkdir()
    files = (
        f'\n[files]\nallowed_roots = ["{workdir}", "{downloads}"]\n'
        f'kit_dir = "{downloads}"\nkit_max_mb = 1\n'
    )
    project = write(tmp_home, workdir, url=ours.base, more=files)
    for server in hosts:
        server.files["/file/k.zip"] = ZIP
    lines: asyncio.Queue[str] = asyncio.Queue()
    handed: list[dict[str, Any]] = []

    async def stream(url: str, **kwargs: Any) -> AsyncIterator[str]:
        handed.append(kwargs)
        while True:
            yield await lines.get()

    def attachment(server: LocalNtfy, name: str) -> dict[str, Any]:
        return {"name": name, "type": "application/zip", "size": len(ZIP),
                "expires": int(time.time()) + 3600, "url": f"{server.base}/file/k.zip"}  # fmt: skip

    async def scenario() -> None:
        daemon = Daemon(load_config(project))
        ntfy = DenyAll()
        daemon.notifier.post = partial(http_post, transport=ntfy.transport)
        assert daemon.phone is not None
        daemon.phone.stream = stream
        daemon.phone.sleep = no_sleep
        await daemon.start()
        try:
            for server, name in ((ours, "ours.zip"), (foreign, "foreign.zip")):
                before = daemon.phone.handled
                lines.put_nowait(stream_line(f"kit {SECRET}", attachment=attachment(server, name)))

                async def read(before: int = before) -> bool:
                    return daemon.phone is not None and daemon.phone.handled > before

                await poll(read, f"the channel to read the kit {name}")
            await daemon.notifier.drain()
            received = [e.payload["name"] for e in daemon.spool.events()
                        if e.kind == "kit.received"]  # fmt: skip
            assert received == ["ours.zip", "foreign.zip"]
            titles = [request.headers.get("Title") for request in ntfy.requests]
            assert titles.count(KIT_TITLE) == 2
            assert set(ntfy.auth()) == {BEARER}
        finally:
            await daemon.stop()

    asyncio.run(scenario())
    assert handed == [{"token": TOKEN}]  # the subscription is handed the token too
    assert ours.auth == [BEARER]
    assert foreign.auth == [None]
    assert (downloads / "ours.zip").read_bytes() == ZIP
    assert_no_token(caplog.text)


def test_the_bearer_goes_to_ntfy_urls_origin_and_nowhere_else() -> None:
    same = phone_mod.attachment_token
    assert same("https://ntfy.tail.ts.net/file/a.zip", "https://ntfy.tail.ts.net", TOKEN) == TOKEN
    assert same("https://NTFY.tail.ts.net:443/file/a.zip", "https://ntfy.tail.ts.net/", TOKEN) == (
        TOKEN
    )
    for url in (
        "http://ntfy.tail.ts.net/file/a.zip",  # another scheme
        "https://ntfy.tail.ts.net:8443/file/a.zip",  # another port
        "https://ntfy.tail.ts.net.evil.example/file/a.zip",  # another host
        "https://ntfy.sh/file/a.zip",
    ):
        assert same(url, "https://ntfy.tail.ts.net", TOKEN) is None, url
    assert same("https://ntfy.tail.ts.net/file/a.zip", "https://ntfy.tail.ts.net", None) is None


# ------------------------------------------------------------------ handswho


def who_sources() -> who.Sources:
    return who.Sources(
        project=PROJECT,
        role_cwds={},
        daemon=lambda: None,
        procs=dict,
        transcripts=lambda _pid, _cwd, _age, _jobs: ("session", None),
        clock=lambda: 1000.0,
        home=Path("/nonexistent-home"),
        job_sessions=frozenset,
        session_of=lambda _pid: None,
    )


@pytest.mark.parametrize("token", [TOKEN, None], ids=["token", "no_token"])
def test_handswho_publishes_and_subscribes_with_the_bearer(token: str | None) -> None:
    started = 5000
    request_line = json.dumps({"event": "message", "id": "w1", "time": started + 1,
                               "message": "who"})  # fmt: skip
    ntfy = DenyAll([json.dumps({"event": "open"}), request_line])
    pusher = who.WhoPusher(
        who_sources(),
        topic=WHO_TOPIC,
        cmd_topic=WHO_CMD_TOPIC,
        ntfy_url=NTFY,
        token=token,
        post=partial(http_post, transport=ntfy.transport),
        stream=partial(http_stream, transport=ntfy.transport),
        clock=lambda: float(started),
    )

    async def scenario() -> bool:
        pushed = await pusher.scan()
        pusher.start_commands()
        try:
            await pusher.subscribe_once()
        except httpx.HTTPStatusError:
            assert token is None
        return pushed

    pushed = asyncio.run(scenario())
    paths = [(request.method, request.url.path) for request in ntfy.requests]
    if token is not None:
        assert pushed is True
        assert paths == [
            ("POST", f"/{WHO_TOPIC}"),
            ("GET", f"/{WHO_CMD_TOPIC}/json"),
            ("POST", f"/{WHO_TOPIC}"),
        ]
        assert ntfy.auth() == [BEARER] * 3
    else:
        assert pushed is False
        assert paths == [("POST", f"/{WHO_TOPIC}"), ("GET", f"/{WHO_CMD_TOPIC}/json")]
        assert ntfy.auth() == [None, None]


def test_handswho_is_handed_the_configured_token(
    tmp_home: Path, workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_config(write(tmp_home, workdir))
    seen: list[str | None] = []

    async def run(self: who.WhoPusher) -> None:
        seen.append(self.token)

    monkeypatch.setattr(who.WhoPusher, "run", run)
    assert who.watch(config, tmp_home / "none.sock") == 0
    assert seen == [TOKEN]


# ------------------------------------------------------------------- doctor


@pytest.mark.parametrize("token", [TOKEN, None], ids=["on", "off"])
def test_doctor_shows_the_token_on_or_off_and_never_its_value(
    tmp_home: Path, workdir: Path, token: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANDS_DOCTOR_FAKE", "1")
    project = write(tmp_home, workdir, token=token)
    _, text, text_err = run_cli(project, "doctor")
    _, raw, raw_err = run_cli(project, "--json", "doctor")
    rows = {check["name"]: check for check in json.loads(raw)["checks"]}
    detail = rows["notifications"]["detail"]
    said = "ntfy token on" if token else "ntfy token off"
    other = "ntfy token off" if token else "ntfy token on"
    assert said in strip_paths(detail)
    assert other not in strip_paths(detail)
    assert said in strip_paths(text)
    assert rows["notifications"]["status"] == "ok"
    assert_no_token(text, text_err, raw, raw_err)
