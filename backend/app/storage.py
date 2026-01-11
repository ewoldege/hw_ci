import os
from typing import BinaryIO

import boto3


class Storage:
    def __init__(self) -> None:
        self.endpoint_url = os.getenv("S3_ENDPOINT_URL")
        self.access_key = os.getenv("S3_ACCESS_KEY")
        self.secret_key = os.getenv("S3_SECRET_KEY")
        self.bucket = os.getenv("S3_BUCKET", "hwci-artifacts")

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def ensure_bucket(self) -> None:
        buckets = self.client.list_buckets().get("Buckets", [])
        if not any(b["Name"] == self.bucket for b in buckets):
            self.client.create_bucket(Bucket=self.bucket)

    def put_object(self, key: str, data: BinaryIO, content_type: str | None) -> None:
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)

    def presign_get(self, key: str, expires_in: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )
