"""SQLite-first test defaults; production adapters/configuration stay unchanged."""
import builtins
from contextlib import closing
import importlib
import io
import ipaddress
import os
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
# Publicly declared Rahtal fallback locations. Never inspect their contents.
PRIVATE_ENV = frozenset(path.resolve() for path in (
    ROOT / ".env", ROOT / "sageql_rahtal/.env", ROOT.parent / "rahtal-be/.env",
    ROOT.parent / "ZarProject/rahtal-be/.env", Path("D:/Coding/QuerySmith/rahtal/.env"),
))


def _guard_open(delegate):
    def guarded(file, *args, **kwargs):
        if isinstance(file, (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(file))
            # Most evaluator reads are ordinary source/JSON files. Resolve only
            # environment candidates or file aliases, avoiding a path-component
            # stat walk for every read on mounted/remote development filesystems.
            if ((path.name.casefold() == ".env" or path.is_symlink())
                    and path.resolve() in PRIVATE_ENV):
                raise AssertionError("Tests cannot access production environment files; use tmp_path settings")
        return delegate(file, *args, **kwargs)
    return guarded


def _loopback(host):
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _local_connection(delegate):
    def guarded(owner, address, *args, **kwargs):
        if not isinstance(address, tuple) or not _loopback(address[0]):
            raise AssertionError("Offline tests allow only loopback HTTP; use a fake external transport")
        return delegate(owner, address, *args, **kwargs)
    return guarded


def pytest_addoption(parser):
    parser.addoption("--run-sqlserver-integration", action="store_true", default=False,
                     help="Enable native SQL Server tests only with separate approved synthetic configuration")


def _native_requested(config):
    # PYTEST_ADDOPTS/ini defaults cannot turn an ordinary run into a native run.
    return (config.getoption("--run-sqlserver-integration")
            and "--run-sqlserver-integration" in config.invocation_params.args)


def pytest_configure(config):
    patch = pytest.MonkeyPatch()
    config._sageql_offline_patch = patch
    patch.setattr(builtins, "open", _guard_open(builtins.open))
    patch.setattr(io, "open", _guard_open(io.open))
    if _native_requested(config):
        return
    patch.setattr(socket.socket, "connect", _local_connection(socket.socket.connect))
    patch.setattr(socket.socket, "connect_ex", _local_connection(socket.socket.connect_ex))
    resolve = socket.getaddrinfo
    def local_resolution(host, *args, **kwargs):
        if not _loopback(host):
            raise AssertionError("Offline tests cannot resolve external hosts")
        return resolve(host, *args, **kwargs)
    patch.setattr(socket, "getaddrinfo", local_resolution)
    try:
        driver = importlib.import_module("pyodbc")
    except ImportError:
        pass  # The ordinary suite does not require the optional ODBC extra.
    else:
        def no_native_connection(*args, **kwargs):
            raise AssertionError("Native SQL Server requires --run-sqlserver-integration and separate authorization")
        patch.setattr(driver, "connect", no_native_connection)


def pytest_unconfigure(config):
    patch = getattr(config, "_sageql_offline_patch", None)
    if patch is not None:
        patch.undo()


def pytest_collection_modifyitems(config, items):
    if _native_requested(config):
        return
    skip = pytest.mark.skip(reason="Native SQL Server disabled; use --run-sqlserver-integration after separate synthetic-target approval")
    for item in items:
        if item.get_closest_marker("sqlserver_integration"):
            item.add_marker(skip)


@pytest.fixture
def sqlite_host_factory(tmp_path):
    """Reuse the existing evaluation seed/catalog/policy; one fresh file per call."""
    from evaluations.phase03_hosts import host
    from sageql.sdk import SQLiteAdapter
    import sqlite3
    created = 0
    def create(domain="retail", *, wal=False):
        nonlocal created
        directory = tmp_path / f"{domain}-{created}"
        created += 1
        directory.mkdir()
        path = directory / "report.sqlite"
        catalog, policy, seed = host(domain)
        seed(path)
        if wal:
            with closing(sqlite3.connect(path)) as connection:
                assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        return SimpleNamespace(path=path, catalog=catalog, policy=policy, database=SQLiteAdapter(path))
    return create
