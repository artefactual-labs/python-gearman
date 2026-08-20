===============
Design document
===============

Architectural design document for developers

GearmanConnectionManager - Bridges low-level I/O <-> command handlers
=====================================================================
* Only class that an API user should directly interact with
* Manages all I/O: polls connections, reconnects failed connections, etc...
* Forwards commands between Connections <-> CommandHandlers
* Manages multiple Connections and multple CommandHandlers
* Manages global state of an interaction with Gearman (global job lock)

GearmanConnection - Manages low-level I/O
=========================================
* A single connection between a client/worker and a server
* Thinly wrapped socket that can reconnect
* Converts binary strings <-> Gearman commands
* Manages in/out data buffers for socket-level operations
* Manages in/out command buffers for gearman-level operations

Connection transport policy
---------------------------
``GearmanConnection`` resolves its configured hostname whenever it creates a
new TCP connection.  ``socket.create_connection`` also tries each address
returned by the resolver.  The following class attributes allow applications
to configure connection establishment and TCP keepalive without changing the
constructor API::

    class DeploymentConnection(GearmanConnection):
        connect_timeout = 5.0
        keepalive = True
        keepalive_idle = 60
        keepalive_interval = 10
        keepalive_count = 3

The defaults preserve the historical behavior: no explicit connection timeout
and no client-side TCP keepalive.  The ``TCP_KEEP*`` settings are applied only
when the platform exposes the corresponding socket option.

Keepalive can make the operating system detect a dead peer while an otherwise
idle connection is open.  It does not reconnect the connection.  The
connection manager or application must respond to the resulting I/O failure by
establishing a new connection.

GearmanCommandHandler - Manages commands
========================================
* Represents the state machine of a single GearmanConnection
* 1-1 mapping to a GearmanConnection (via GearmanConnectionManager)
* Sends/receives commands ONLY - does no buffering
* Handles all command generation / interpretation
