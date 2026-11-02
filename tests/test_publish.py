import json

import pytest

from autopost_kit.core.publish import publish_reel
from autopost_kit.core.publishers.instagram import InstagramClient, InstagramError
from autopost_kit.core.storage import S3Storage


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


class FakeGraph:
    """Answers Graph API calls from a list of (method, path suffix, payload)."""

    def __init__(self, routes):
        self.routes = list(routes)
        self.calls = []

    def request(self, method, url, timeout=None, params=None, data=None):
        sent = params or data or {}
        self.calls.append((method, url, {k: v for k, v in sent.items() if k != "access_token"}))
        for i, (m, suffix, payload, *status) in enumerate(self.routes):
            if m == method and url.endswith(suffix):
                self.routes.pop(i)
                return FakeResponse(payload, *(status or [200]))
        raise AssertionError(f"unexpected call {method} {url}")


class FakeS3:
    def __init__(self):
        self.uploaded, self.deleted = [], []

    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.uploaded.append((bucket, key, ExtraArgs["ContentType"]))

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://s3.example/{Params['Key']}?expires={ExpiresIn}"

    def delete_object(self, Bucket, Key):
        self.deleted.append(Key)


def client(routes):
    graph = FakeGraph(routes)
    return InstagramClient("TOKEN", session=graph, sleep=lambda s: None), graph


def test_user_id_comes_from_assigned_accounts():
    ig, graph = client([("GET", "/me/assigned_instagram_accounts", {"data": [{"id": "1784", "username": "tomorrowonsteam"}]})])

    assert ig.user_id == "1784"
    assert ig.user_id == "1784"  # cached: only one call
    assert len(graph.calls) == 1


def test_api_errors_are_readable():
    ig, _ = client([("GET", "/me/assigned_instagram_accounts", {"error": {"message": "Invalid OAuth access token"}}, 400)])

    with pytest.raises(InstagramError, match="Invalid OAuth access token"):
        ig.user_id


def test_dry_run_processes_but_does_not_publish(tmp_path):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"fake")
    ig, graph = client([
        ("GET", "/me/assigned_instagram_accounts", {"data": [{"id": "1784"}]}),
        ("POST", "/1784/media", {"id": "C1"}),
        ("GET", "/C1", {"status_code": "IN_PROGRESS"}),
        ("GET", "/C1", {"status_code": "FINISHED"}),
    ])
    s3 = FakeS3()

    result = publish_reel(video, "caption", ig, S3Storage("bucket", "us-east-2", client=s3))

    assert not result.published
    assert s3.uploaded[0][2] == "video/mp4"
    assert s3.deleted == [s3.uploaded[0][1]]  # cleaned up right after processing
    create = next(c for c in graph.calls if c[0] == "POST")
    assert create[2]["media_type"] == "REELS"
    assert create[2]["video_url"].startswith("https://s3.example/reels/")
    assert not any("media_publish" in c[1] for c in graph.calls)


def test_confirmed_publish_returns_permalink(tmp_path):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"fake")
    ig, _ = client([
        ("GET", "/me/assigned_instagram_accounts", {"data": [{"id": "1784"}]}),
        ("POST", "/1784/media", {"id": "C1"}),
        ("GET", "/C1", {"status_code": "FINISHED"}),
        ("POST", "/1784/media_publish", {"id": "M1"}),
        ("GET", "/M1", {"permalink": "https://www.instagram.com/reel/abc/"}),
    ])

    result = publish_reel(video, "caption", ig, S3Storage("b", "r", client=FakeS3()), confirm=True)

    assert result.published and result.permalink == "https://www.instagram.com/reel/abc/"


def test_processing_error_still_deletes_upload(tmp_path):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"fake")
    ig, _ = client([
        ("GET", "/me/assigned_instagram_accounts", {"data": [{"id": "1784"}]}),
        ("POST", "/1784/media", {"id": "C1"}),
        ("GET", "/C1", {"status_code": "ERROR", "status": "Unsupported video"}),
    ])
    s3 = FakeS3()

    with pytest.raises(InstagramError, match="Unsupported video"):
        publish_reel(video, "caption", ig, S3Storage("b", "r", client=s3))
    assert len(s3.deleted) == 1


def test_publish_is_not_retried_when_it_already_went_out():
    ig, graph = client([
        ("POST", "/1784/media_publish", {"error": {"message": "timeout"}}, 500),
        ("GET", "/C1", {"status_code": "PUBLISHED"}),
        ("GET", "/1784/media", {"data": [{"id": "M9"}]}),
    ])
    ig._user_id = "1784"

    assert ig.publish("C1") == "M9"
    assert sum(1 for c in graph.calls if "media_publish" in c[1]) == 1
