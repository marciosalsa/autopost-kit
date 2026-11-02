"""Temporary public links for media, so Instagram can fetch it.

The bucket stays private: each file gets a pre-signed link that expires, and
the file is deleted as soon as Instagram has processed it. A lifecycle rule on
the bucket deletes anything left behind after one day.
"""

from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

_KNOWN_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


class S3Storage:
    def __init__(self, bucket: str, region: str, client=None, link_seconds: int = 3600) -> None:
        if client is None:
            import boto3  # imported lazily: only needed when publishing
            from botocore.config import Config

            # Regional endpoint + SigV4: links signed against the global
            # endpoint fail with SignatureDoesNotMatch for buckets outside
            # us-east-1, and Instagram then cannot fetch the media.
            client = boto3.client(
                "s3",
                region_name=region,
                endpoint_url=f"https://s3.{region}.amazonaws.com",
                config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
            )
        self.client = client
        self.bucket = bucket
        self.link_seconds = link_seconds

    def upload(self, path: Path | str, prefix: str = "media") -> tuple[str, str]:
        """Upload ``path`` and return ``(key, temporary_url)``."""
        path = Path(path)
        key = f"{prefix}/{uuid.uuid4().hex}{path.suffix.lower()}"
        # Don't rely on the OS registry (Windows can map these oddly).
        content_type = _KNOWN_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.client.upload_file(str(path), self.bucket, key, ExtraArgs={"ContentType": content_type})
        url = self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=self.link_seconds
        )
        log.info("Uploaded %s to s3://%s/%s", path.name, self.bucket, key)
        return key, url

    def delete(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            log.info("Deleted s3://%s/%s", self.bucket, key)
        except Exception as exc:  # the lifecycle rule is the safety net
            log.warning("Could not delete s3://%s/%s (%s); the 1-day rule will remove it.", self.bucket, key, exc)
