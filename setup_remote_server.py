#!/usr/bin/python3
"""
Sets up a remote server for access over WireGuard and creates a corresponding
local config file.

WARNING: this will sudo on the server and meddle with the WireGuard
configuration, firewall and systemd services.

Whilst the resulting configuration is intended to be used for temporary
point-to-point connections, it includes 'random' local and remote internal IPs
based on the hash of the remote server and local user names. This should mean
that:

- Multiple users are likely to have different local internal IPs so can share
  the same remote configuration.

- Different servers are likely to have different remote internal IPs (and the
  configurations different local internal IPs) so that multiple non-conflicting
  connections to different servers could be made at the same time if desired.


"""

import base64
import hashlib
import getpass
import json
import shlex
import subprocess
import struct
import sys
import time

def hash_ip_segment(s, num_octets):
    # hash to a 32-bit int
    v, = struct.unpack("I", hashlib.sha1(s.encode('ascii')).digest()[:4])
    # avoid a last octet of .255
    ret, v = [str(v%255)], v//255
    for n in range(num_octets-1):
        ret.append(str(v&0xff))
        v >>= 8
    return ".".join(ret[::-1])

remote_host = sys.argv[1]
local_internal_ip = '10.202.' + hash_ip_segment(getpass.getuser() + '@' + remote_host.split("@")[-1], 2)
remote_internal_ip = '10.203.' + hash_ip_segment(remote_host.split("@")[-1], 2)
remote_external_port = 51232
wireguard_interface = "wg99"

local_private_key = subprocess.check_output(["wg", "genkey"]).decode('ascii').strip()
local_public_key = subprocess.check_output(["wg", "pubkey"], input=local_private_key.encode('ascii')).decode('ascii').strip()

script = '''

import json
import os
import subprocess
import sys

os.umask(0o077)

data = json.loads(\'''' + json.dumps({
    'local_internal_ip': local_internal_ip,
    'remote_internal_ip': remote_internal_ip,
    'local_public_key': local_public_key,
    'remote_external_port': str(remote_external_port),
    'wireguard_interface': wireguard_interface,
}) + '''\')

wireguard_config_file = "/etc/wireguard/%s.conf" % data['wireguard_interface']

if os.path.exists(wireguard_config_file):
    chunks = open(wireguard_config_file).read().split('[Peer]')

    def parse_chunk(chunk):
        return dict(
            [bit.strip() for bit in line.split('=', 1)]
            for line in chunk.split('\\n') if '=' in line
        )

    interface = parse_chunk(chunks[0])

    data['remote_internal_ip'] = interface['Address'].split('/')[0]

    peers = [
        parse_chunk(chunk)
        for chunk in chunks[1:]
    ]

    #strip out existing matching peers
    peers = [
        p
        for p in peers
        if p['PublicKey']!=data['local_public_key'] and p['AllowedIPs']!=(data['local_internal_ip']+'/32')
    ]
else:
    interface = {
        'Address': data['remote_internal_ip']+'/32',
        'ListenPort': data['remote_external_port'],
        'PrivateKey': subprocess.check_output(["wg", "genkey"]).decode('ascii').strip()
    }
    peers = []

peers.append({
    'PublicKey': data['local_public_key'],
    'AllowedIPs': data['local_internal_ip']+'/32'
})

conf = '[Interface]\\n' + '\\n'.join('%s = %s'%i for i in interface.items())
for peer in peers:
    conf += '\\n\\n[Peer]\\n' + '\\n'.join('%s = %s'%i for i in peer.items())

open(wireguard_config_file, "w").write(conf + '\\n')

public_key = subprocess.check_output(["wg", "pubkey"], input=interface['PrivateKey'].encode('ascii')).decode('ascii').strip()
print('REMOTE_INTERNAL_IP[' + data['remote_internal_ip'] + ']')
print('PUBLIC_KEY[' + public_key + ']')

if os.path.exists('/usr/sbin/ufw'):
    subprocess.call(["ufw", "allow", data['remote_external_port'] + "/udp"])
    subprocess.call(["ufw", "allow", "from", data['local_internal_ip'], "to", "any", "port", "22"])

subprocess.call(["systemctl", "enable", "wg-quick@" + data['wireguard_interface']])
subprocess.call(["wg-quick", "down", data['wireguard_interface']])
subprocess.call(["wg-quick", "up", data['wireguard_interface']])

'''

output = ""

process = subprocess.Popen([
    "ssh", "-t", remote_host,
    "sudo python3 -c 'import base64; exec(base64.b64decode(\"%s\").decode(\"utf-8\"));' >&2"%base64.b64encode(script.encode('utf-8')).decode('ascii'),
], stdout=subprocess.PIPE)
for c in iter(lambda: process.stdout.read(1).decode('ascii', 'ignore'), ''):
    sys.stdout.write(c)
    sys.stdout.flush()
    output += c
    if c=='':
        time.sleep(0.5)
process.communicate()

if process.returncode != 0:
    print(output)
    sys.exit(1)

remote_internal_ip = output.strip().split('REMOTE_INTERNAL_IP[')[1].split(']')[0]    
remote_public_key = output.strip().split('PUBLIC_KEY[')[1].split(']')[0]

if len(remote_public_key)!=44:
    print("Remote public key is wrong length:", remote_public_key)
    sys.exit(1)

open(remote_host.split('@')[-1] + ".conf", "w").write("""[Interface]
Address = %s/32
PrivateKey = %s

[Peer]
PublicKey = %s
AllowedIPs = %s/32
Endpoint = %s:%s
"""%(
    local_internal_ip,
    local_private_key,
    remote_public_key,
    remote_internal_ip,
    remote_host.split('@')[-1],
    remote_external_port
))

print('Successfully created configuration.')
