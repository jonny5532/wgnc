/* 
 * wgnc - a netcat-like program for creating TCP connections over WireGuard tunnels
 * 
 * SPDX-License-Identifier: MIT
 *
 * Based on https://git.zx2c4.com/wireguard-go/tree/tun/netstack/examples/ping_client.go
 * Copyright (C) 2019-2021 WireGuard LLC. All Rights Reserved.
 *
 */

package main

import (
	"context"
	"encoding/base64"
	"encoding/hex"
	"errors"
    "flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/netip"
	"os"
	"regexp"
	"strconv"
	"strings"

	"golang.zx2c4.com/wireguard/conn"
	"golang.zx2c4.com/wireguard/device"
	"golang.zx2c4.com/wireguard/tun/netstack"
)

func base64ToHex(s string) string {
	k, _ := base64.StdEncoding.DecodeString(s)
	return  hex.EncodeToString(k)
}

type Config struct {
    LocalInternalIP      netip.Addr `json:"local_internal_ip"`
    LocalPrivateKey      string     `json:"local_private_key"`

	RemoteExternalHost   string     `json:"remote_external_host"`
	RemoteExternalPort   uint16     `json:"remote_external_port"`
	RemotePublicKey      string     `json:"remote_public_key"`

	RemoteConnectIP      netip.Addr `json:"remote_connect_ip"`
	RemoteConnectPort    uint16     `json:"remote_connect_port"`
}

func parseChunk(chunk string) map[string]string {
	ret := make(map[string]string)
	for _, line := range strings.Split(chunk, "\n") {
		line = strings.Split(strings.Split(line, "#")[0], ";")[0]
		bits := strings.SplitN(line, "=", 2)
		if len(bits)<2 {
			continue
		}
		key, value := strings.TrimSpace(bits[0]), strings.TrimSpace(bits[1])
		ret[key] = value
	}
	return ret
}

func parsePort(s string) uint16 {
	port, perr := strconv.ParseUint(s, 10, 16)
	if perr != nil {
		return 0
	}
	return uint16(port)
}

func parseConfig(fn string) (Config, error) {
	var config Config

	dat, err := os.ReadFile(fn)
	if err != nil {
		return config, err
	}

	peerSplit := regexp.MustCompile(`\n\s*\[Peer\]`)
	chunks := peerSplit.Split(string(dat), 50)
	if len(chunks)==1 {
		return config, errors.New("No peers found in configuration.")
	}

	iface := parseChunk(chunks[0])

	config.LocalInternalIP = netip.MustParseAddr(strings.Split(iface["Address"], "/")[0])
	config.LocalPrivateKey = iface["PrivateKey"]

	for _, chunk := range chunks[1:len(chunks)] {
		peer := parseChunk(chunk)

		config.RemotePublicKey = peer["PublicKey"]

		sep_index := strings.LastIndex(peer["Endpoint"], ":")
		if sep_index == -1 {
			continue
		}

		config.RemoteExternalHost = peer["Endpoint"][0:sep_index]
		config.RemoteExternalPort = parsePort(peer["Endpoint"][sep_index+1:len(peer["Endpoint"])])

		remote_internal_ip, err := netip.ParseAddr(strings.Split(peer["AllowedIPs"], "/32")[0])
		if err == nil {
			config.RemoteConnectIP = remote_internal_ip
		}
		
		config.RemoteConnectPort = 22
		
		return config, nil
	}


	return config, errors.New("No suitable peer found.")
}

func GoogleDNSDialer(ctx context.Context, network, address string) (net.Conn, error) {
	d := net.Dialer{}
	return d.DialContext(ctx, "udp", "8.8.8.8:53")
}

func resolveExternalHostPort(host string, port uint16) string {
	r := net.Resolver{
		PreferGo: true,
		Dial: GoogleDNSDialer,
	}
	ctx := context.Background()

	remote_external_ips, err := r.LookupIP(ctx, "ip", host)
	if err != nil || len(remote_external_ips) < 1 {
		log.Panic("Couldn't resolve ", host)
	}

	return net.JoinHostPort(remote_external_ips[0].String(), fmt.Sprintf("%d", port))
}

func main() {
	configFileName := flag.String("c", "", "path to WireGuard config file")
	port := flag.Int("p", 22, "port to connect to (default 22)")
	mtu := flag.Int("mtu", 1420, "tunnel MTU (default 1420)")
	flag.Parse()

	var config Config

	if *configFileName != "" {
		c, err := parseConfig(*configFileName)
		if err != nil {
			log.Panic(err)
		}
		config = c
	} else {
		log.Fatal("Please specify a config file with -c <wireguard.conf>")
	}

	if flag.NArg() >= 1 {
		// host is supplied as an arg
		config.RemoteConnectIP = netip.MustParseAddr(flag.Arg(0))
	}
	
	if !config.RemoteConnectIP.IsValid() {
		log.Fatal("The remote internal IP to connect to was not specified and could not be inferred from the configuration.")
	}

	if flag.NArg() >= 2 {
		// port is supplied as an arg
		config.RemoteConnectPort = parsePort(flag.Arg(1))
	} else {
		// else use flag port (or default)
		config.RemoteConnectPort = uint16(*port)
	}

	tun, tnet, err := netstack.CreateNetTUN(
		[]netip.Addr{config.LocalInternalIP},
		[]netip.Addr{}, // we don't need DNS?
		*mtu)
	if err != nil {
		log.Panic(err)
	}
	dev := device.NewDevice(tun, conn.NewDefaultBind(), device.NewLogger(device.LogLevelError, ""))
	dev.IpcSet(fmt.Sprintf(`private_key=%s
public_key=%s
endpoint=%s
allowed_ip=0.0.0.0/0
`,
		base64ToHex(config.LocalPrivateKey),
		base64ToHex(config.RemotePublicKey),
		resolveExternalHostPort(config.RemoteExternalHost, config.RemoteExternalPort),
	))
	err = dev.Up()
	if err != nil {
		log.Panic(err)
	}

	socket, err := tnet.DialTCPAddrPort(netip.AddrPortFrom(
		config.RemoteConnectIP,
		config.RemoteConnectPort,
	))
	if err != nil {
		log.Panic(err)
	}

	go io.Copy(socket, os.Stdin)
	io.Copy(os.Stdout, socket)
}
