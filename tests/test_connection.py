# -*- encoding: utf-8

import socket

import pytest

from gearman import connection, compat
from gearman.errors import ConnectionError, ServerUnavailable
from gearman.protocol import GEARMAN_COMMAND_TEXT_COMMAND, GEARMAN_COMMAND_ECHO_REQ

from tests._core_testing import random_bytes


class FakeSocket(object):
    def __init__(self):
        self.blocking = []
        self.closed = False
        self.options = []
        self.timeouts = []

    def close(self):
        self.closed = True

    def setblocking(self, value):
        self.blocking.append(value)

    def setsockopt(self, level, option, value):
        self.options.append((level, option, value))

    def settimeout(self, value):
        self.timeouts.append(value)


def test_no_host_is_ServerUnavailable():
    with pytest.raises(ServerUnavailable):
        connection.GearmanConnection(host=None)


@pytest.mark.parametrize('keyfile,certfile,ca_certs,expected_use_ssl', [
    (None, None, None, False),
    ('key.txt', None, None, False),
    (None, 'cert.txt', None, False),
    (None, None, 'ca_certs.txt', False),
    ('key.txt', 'cert.txt', None, False),
    (None, 'cert.txt', 'ca_certs.txt', False),
    ('key.txt', None, 'ca_certs.txt', False),
    ('key.txt', 'cert.txt', 'ca_certs.txt', True)
])
def test_use_ssl_only_if_all_three_files(keyfile, certfile, ca_certs, expected_use_ssl):
    conn = connection.GearmanConnection(
        host='localhost',
        keyfile=keyfile,
        certfile=certfile,
        ca_certs=ca_certs
    )
    assert conn.use_ssl == expected_use_ssl


def test_no_socket_means_no_fileno():
    conn = connection.GearmanConnection(host='localhost')
    with pytest.raises(ConnectionError, match='no socket set'):
        conn.fileno()


def test_connection_defaults_preserve_existing_transport_behavior(monkeypatch):
    created_socket = FakeSocket()
    create_calls = []

    def create_connection(*args, **kwargs):
        create_calls.append((args, kwargs))
        return created_socket

    monkeypatch.setattr(socket, 'create_connection', create_connection)

    conn = connection.GearmanConnection(host='gearman.service')
    conn.connect()

    assert create_calls == [((('gearman.service', 4730),), {})]
    assert conn.gearman_socket is created_socket
    assert created_socket.blocking == [0]
    assert created_socket.timeouts == [0.0]
    assert not any(
        level == socket.SOL_SOCKET and option == socket.SO_KEEPALIVE
        for level, option, value in created_socket.options
    )


def test_configured_transport_options_apply_to_every_new_socket(monkeypatch):
    class ConfiguredConnection(connection.GearmanConnection):
        connect_timeout = 4.5
        keepalive = True
        keepalive_idle = 60
        keepalive_interval = 10
        keepalive_count = 3

    monkeypatch.setattr(socket, 'TCP_KEEPIDLE', 101, raising=False)
    monkeypatch.setattr(socket, 'TCP_KEEPINTVL', 102, raising=False)
    monkeypatch.setattr(socket, 'TCP_KEEPCNT', 103, raising=False)

    created_sockets = []
    create_calls = []

    def create_connection(*args, **kwargs):
        create_calls.append((args, kwargs))
        created_socket = FakeSocket()
        created_sockets.append(created_socket)
        return created_socket

    monkeypatch.setattr(socket, 'create_connection', create_connection)

    conn = ConfiguredConnection(host='gearman.service')
    conn.connect()
    conn.close()
    conn.connect()

    assert create_calls == [
        ((('gearman.service', 4730),), {'timeout': 4.5}),
        ((('gearman.service', 4730),), {'timeout': 4.5}),
    ]
    assert len(created_sockets) == 2
    assert created_sockets[0].closed

    expected_options = {
        (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1),
        (socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 60),
        (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10),
        (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3),
    }
    for created_socket in created_sockets:
        assert expected_options.issubset(set(created_socket.options))


def test_keepalive_uses_platform_defaults_for_unsupported_tuning(monkeypatch):
    class KeepaliveConnection(connection.GearmanConnection):
        keepalive = True
        keepalive_idle = 60
        keepalive_interval = 10
        keepalive_count = 3

    for option_name in (
        'TCP_KEEPIDLE',
        'TCP_KEEPALIVE',
        'TCP_KEEPINTVL',
        'TCP_KEEPCNT',
    ):
        monkeypatch.delattr(socket, option_name, raising=False)

    created_socket = FakeSocket()
    monkeypatch.setattr(
        socket, 'create_connection', lambda *args, **kwargs: created_socket
    )

    KeepaliveConnection(host='gearman.service').connect()

    assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in created_socket.options
    assert not any(
        level == socket.IPPROTO_TCP and option != socket.TCP_NODELAY
        for level, option, value in created_socket.options
    )


def test_socket_is_closed_when_transport_configuration_fails(monkeypatch):
    class BrokenKeepaliveSocket(FakeSocket):
        def setsockopt(self, level, option, value):
            if level == socket.SOL_SOCKET and option == socket.SO_KEEPALIVE:
                raise socket.error('keepalive failed')
            super(BrokenKeepaliveSocket, self).setsockopt(level, option, value)

    class KeepaliveConnection(connection.GearmanConnection):
        keepalive = True

    created_socket = BrokenKeepaliveSocket()
    monkeypatch.setattr(
        socket, 'create_connection', lambda *args, **kwargs: created_socket
    )

    with pytest.raises(ConnectionError, match='keepalive failed'):
        KeepaliveConnection(host='gearman.service').connect()

    assert created_socket.closed


def test_ssl_wraps_the_configured_socket(monkeypatch):
    class KeepaliveConnection(connection.GearmanConnection):
        keepalive = True

    raw_socket = FakeSocket()
    ssl_socket = FakeSocket()
    wrap_calls = []

    monkeypatch.setattr(
        socket, 'create_connection', lambda *args, **kwargs: raw_socket
    )

    def wrap_socket(current_socket, **kwargs):
        assert current_socket is raw_socket
        assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in raw_socket.options
        wrap_calls.append(kwargs)
        return ssl_socket

    monkeypatch.setattr(connection.ssl, 'wrap_socket', wrap_socket, raising=False)

    conn = KeepaliveConnection(
        host='gearman.service',
        keyfile='key.pem',
        certfile='cert.pem',
        ca_certs='ca.pem',
    )
    conn.connect()

    assert conn.gearman_socket is ssl_socket
    assert wrap_calls == [
        {
            'keyfile': 'key.pem',
            'certfile': 'cert.pem',
            'ca_certs': 'ca.pem',
            'cert_reqs': connection.ssl.CERT_REQUIRED,
            'ssl_version': connection.ssl.PROTOCOL_TLSv1,
        }
    ]


def test_reconnect_resolves_the_hostname_again(monkeypatch):
    listeners = []
    accepted_sockets = []
    resolver_results = []

    try:
        for _ in range(2):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(1.0)
            listeners.append(listener)
            resolver_results.append(listener.getsockname())

        resolver_calls = []

        def getaddrinfo(host, port, *args, **kwargs):
            address = resolver_results[len(resolver_calls)]
            resolver_calls.append((host, port))
            return [
                (
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                    socket.IPPROTO_TCP,
                    '',
                    address,
                )
            ]

        monkeypatch.setattr(socket, 'getaddrinfo', getaddrinfo)

        conn = connection.GearmanConnection(host='gearman.service')
        conn.connect()
        accepted_sockets.append(listeners[0].accept()[0])
        conn.close()

        conn.connect()
        accepted_sockets.append(listeners[1].accept()[0])
        conn.close()

        assert resolver_calls == [
            ('gearman.service', 4730),
            ('gearman.service', 4730),
        ]
    finally:
        for accepted_socket in accepted_sockets:
            accepted_socket.close()
        for listener in listeners:
            listener.close()


def test_send_commands_to_buffer():
    conn = connection.GearmanConnection(host='localhost')
    assert conn.send_commands_to_buffer() is None
    assert conn._outgoing_buffer == b''
    conn._outgoing_commands.append((GEARMAN_COMMAND_ECHO_REQ, {"data": "test"}))
    conn.send_commands_to_buffer()
    assert conn._outgoing_buffer == b"\x00REQ\x00\x00\x00\x10\x00\x00\x00\x04test"
    if compat.PY3:
        assert isinstance(conn._outgoing_buffer, compat.binary_type)
    else:
        assert isinstance(conn._outgoing_buffer, compat.binary_type)
    conn._reset_connection()
    conn._outgoing_commands.append((GEARMAN_COMMAND_TEXT_COMMAND, {"raw_text": "raw---text"}))
    conn.send_commands_to_buffer()
    assert conn._outgoing_buffer == b"raw---text"
    if compat.PY3:
        assert isinstance(conn._outgoing_buffer, compat.binary_type)
    else:
        assert isinstance(conn._outgoing_buffer, compat.binary_type)


def test_read_data_from_socket(monkeypatch):
    conn = connection.GearmanConnection(host='localhost')
    b = random_bytes()

    class MockSocket(object):
        def recv(self, bytes_to_read):
            return b

    def create_mock_socket():
        conn.gearman_socket = MockSocket()

    with monkeypatch.context() as m:
        m.setattr(conn, "_create_client_socket", create_mock_socket)
        conn.connect()
    assert conn.read_data_from_socket() == len(b)
