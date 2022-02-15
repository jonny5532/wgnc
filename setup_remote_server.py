#!/usr/bin/python3
"""
Sets up a remote server 


"""

import base64
import json
import shlex
import subprocess
import sys
import time

local_internal_ip = '10.202.23.100'
remote_internal_ip = '10.202.23.1'
remote_external_port = 51232
wireguard_interface = "wg99"

remote_host = sys.argv[1]
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

    if interface['Address']!=data['remote_internal_ip']:
        print('Existing configuration has an incompatible remote internal IP!')
        sys.exit(1)

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
        'Address': data['remote_internal_ip'],
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


# open(remote_host.split('@')[-1] + ".json", "w").write(json.dumps({
#     'local_internal_ip': local_internal_ip,
#     "local_private_key": local_private_key,

#     'remote_internal_ip': remote_internal_ip,
#     "remote_external_host": remote_host,
#     "remote_external_port": remote_external_port,
#     "remote_public_key": remote_public_key,

#     "remote_connect_ip": remote_internal_ip,
#     "remote_connect_port": 22
# }, indent=4))

print('ok')
