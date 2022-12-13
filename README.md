# wgnc

A netcat-alike tool that can open a TCP connection over WireGuard, using
wireguard-go's user-space networking stack.

Allows you to easily SSH over WireGuard without having to set up a local
WireGuard interface first.


## Caveats

- The code lacks proper error handling, particularly the
  WireGuard configuration parsing and network connection state handling.

- The code is poorly tested, use at your own risk!


## Building

If you have Docker installed, you can build with:

`./build.sh`

which will place `wgnc` in the same directory.

You may need to supply the `GOOS` and `GOARCH` environment variables in the
Dockerfile to build for other architectures.


## Usage (with SSH)

1. Create a WireGuard keypair, and register it with the server, as normal.

2. Create a local config file in the format expected by `wg-quick`. The first
   peer in the file will be the one used for connecting.

3. Use `ProxyCommand` with SSH:

`ssh -o ProxyCommand="./wgnc -c wg0.conf 10.0.0.1 22" user@server`

where `10.0.0.1` is the internal IP of the remote peer. If the first entry in
the `AllowedIPs` for the peer is a `/32`, and the desired port is `22`, then
this can be omitted:

`ssh -o ProxyCommand="./wgnc -c wg0.conf" user@server`


## Using `setup_remote_server.py` script

You can use the `setup_remote_server.py <host>` script to set up WireGuard on a
server and generate a corresponding config file.

This script is very hacky - it will sudo on the remote host and meddle with the
WireGuard configuration, firewall and systemd services, be warned!
