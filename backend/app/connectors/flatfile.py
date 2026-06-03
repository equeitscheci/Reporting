"""Flat-file connector: CSV / Excel from local FS, S3, or SFTP.

Incremental for files is by *file-level* watermark (filename or mtime) — new/changed files since the
last sync are processed. Per-row delta detection is handled downstream by the mapping `_hash`.
"""

from __future__ import annotations

import csv
import glob
import io
import logging
import os
from collections.abc import Iterator
from typing import Any

from app.connectors.registry import registry
from app.connectors.sdk import (
    ConnectionStatus,
    Connector,
    ConnectorConfig,
    FieldSchema,
    Record,
    StreamConfig,
    StreamSchema,
    SyncState,
)

logger = logging.getLogger("insightforge.connectors.flatfile")


@registry.register("flatfile")
class FlatFileConnector(Connector):
    def __init__(self, config: ConnectorConfig, secret_resolver: Any | None = None) -> None:
        super().__init__(config, secret_resolver)
        self.root = config.options.get("root_path", ".")
        self.protocol = config.options.get("protocol", "local")  # local|s3|sftp
        self._injected = config.options.get("_files")  # {filename: csv_text} for tests

    def test_connection(self) -> ConnectionStatus:
        try:
            files = self._list_files(self.config.streams[0]) if self.config.streams else []
            return ConnectionStatus(ok=True, discovered_streams=len(self.config.streams),
                                    message=f"{len(files)} file(s) visible")
        except Exception as exc:  # noqa: BLE001
            return ConnectionStatus(ok=False, message=str(exc))

    def discover(self) -> list[StreamSchema]:
        out = []
        for s in self.config.streams:
            fields: list[FieldSchema] = []
            files = self._list_files(s)
            if files:
                rows = list(self._read_file(files[0]))
                if rows:
                    fields = [FieldSchema(name=k, type="string") for k in rows[0]]
            out.append(
                StreamSchema(name=s.name, primary_key=s.primary_key,
                             cursor_field="_source_file", fields=fields)
            )
        return out

    def read(self, stream: str, state: SyncState) -> Iterator[Record]:
        s = self.stream_config(stream)
        last_file = state.cursor_for(stream)
        for fname in sorted(self._list_files(s)):
            if last_file is not None and fname <= last_file:
                continue  # already processed in a prior run
            for row in self._read_file(fname):
                row["_source_file"] = os.path.basename(fname)
                yield Record(stream=stream, data=row)
            state.advance(stream, fname)

    # --------------------------------------------------------------- io
    def _list_files(self, s: StreamConfig) -> list[str]:
        if self._injected is not None:
            return [f for f in self._injected if _matches(f, s)]
        pattern = os.path.join(self.root, s.path or "*.csv")
        if self.protocol == "local":
            return glob.glob(pattern)
        if self.protocol == "s3":
            return self._list_s3(pattern)
        if self.protocol == "sftp":
            return self._list_sftp(pattern)
        raise ValueError(f"Unknown protocol {self.protocol}")

    def _read_file(self, fname: str) -> Iterator[dict[str, Any]]:
        text = self._read_bytes(fname)
        if fname.lower().endswith((".xlsx", ".xls")):
            yield from self._read_excel(text)
        else:
            reader = csv.DictReader(io.StringIO(text))
            yield from reader

    def _read_bytes(self, fname: str) -> str:
        if self._injected is not None:
            return self._injected[fname]
        if self.protocol == "local":
            with open(fname, encoding="utf-8") as fh:
                return fh.read()
        if self.protocol == "s3":
            return self._read_s3(fname)
        if self.protocol == "sftp":
            return self._read_sftp(fname)
        raise ValueError(self.protocol)

    def _read_excel(self, raw: str) -> Iterator[dict[str, Any]]:
        import pandas as pd  # lazy

        df = pd.read_excel(io.BytesIO(raw.encode("latin-1")))
        for rec in df.to_dict(orient="records"):
            yield rec

    # S3 / SFTP are thin wrappers; credentials come from the vault, never inline.
    def _list_s3(self, pattern: str) -> list[str]:  # pragma: no cover - infra
        import boto3  # type: ignore

        bucket, _, prefix = pattern.replace("s3://", "").partition("/")
        s3 = boto3.client("s3")
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [f"s3://{bucket}/{o['Key']}" for o in resp.get("Contents", [])]

    def _read_s3(self, fname: str) -> str:  # pragma: no cover - infra
        import boto3  # type: ignore

        bucket, _, key = fname.replace("s3://", "").partition("/")
        s3 = boto3.client("s3")
        return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")

    def _list_sftp(self, pattern: str) -> list[str]:  # pragma: no cover - infra
        import paramiko  # type: ignore

        host = self.secret(self.config.options.get("sftp_host_ref"))
        user = self.secret(self.config.options.get("sftp_user_ref"))
        pw = self.secret(self.config.options.get("sftp_password_ref"))
        transport = paramiko.Transport((host, 22))
        transport.connect(username=user, password=pw)
        sftp = paramiko.SFTPClient.from_transport(transport)
        d = os.path.dirname(pattern) or "."
        return [os.path.join(d, f) for f in sftp.listdir(d)]

    def _read_sftp(self, fname: str) -> str:  # pragma: no cover - infra
        import paramiko  # type: ignore

        host = self.secret(self.config.options.get("sftp_host_ref"))
        user = self.secret(self.config.options.get("sftp_user_ref"))
        pw = self.secret(self.config.options.get("sftp_password_ref"))
        transport = paramiko.Transport((host, 22))
        transport.connect(username=user, password=pw)
        sftp = paramiko.SFTPClient.from_transport(transport)
        with sftp.open(fname) as fh:
            return fh.read().decode("utf-8")


def _matches(fname: str, s: StreamConfig) -> bool:
    import fnmatch

    return fnmatch.fnmatch(os.path.basename(fname), os.path.basename(s.path or "*"))
