# wgnc

A netcat-alike tool that can open a TCP connection over WireGuard, using
wireguard-go's user-space networking stack.

Allows you to easily SSH over WireGuard without having to set up a local
WireGuard interface first.

## Usage (with SSH)

1. Create a WireGuard keypair, and register it with the server, as normal.

2. Create a JSON config file for the server:

```
{
    "local_internal_ip": "10.0.0.100",
    "local_private_key": "<base64 private key for a peer known by the server>",

	"remote_internal_ip": "10.0.0.1",
	"remote_external_ip": "<public IP of the server>",
    "remote_external_port": <port number on the server that WireGuard is listening on>,
    "remote_public_key": "<base64 public key of server you are connecting to>",

    "remote_connect_ip": "10.0.0.1",
	"remote_connect_port": 22
}
```

3. Use `ProxyCommand` with SSH:

`ssh -o ProxyCommand="./wgnc -c config.json" user@server`

## Using `setup_server.py` script

You can use the `setup_server.py` script to set up WireGuard on a server and generate a corresponding json file.
