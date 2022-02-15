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
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
    "flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net"
	"os"

	"golang.zx2c4.com/go118/netip"
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

	RemoteInternalIP     netip.Addr `json:"remote_internal_ip"`
	RemoteExternalHost   string     `json:"remote_external_host"`
	RemoteExternalPort   uint16     `json:"remote_external_port"`
	RemotePublicKey      string     `json:"remote_public_key"`

	RemoteConnectIP      netip.Addr `json:"remote_connect_ip"`
	RemoteConnectPort    uint16     `json:"remote_connect_port"`
}

func resolveExternalHostPort(host string, port uint16) string {
	remote_external_ips, err := net.LookupIP(host)
	if err != nil || len(remote_external_ips) < 1 {
		log.Panic("Couldn't resolve", host)
	}

	return net.JoinHostPort(remote_external_ips[0].String(), fmt.Sprintf("%d", port))
}

func main() {
	configFileName := flag.String("c", "", "path to JSON config file")
	flag.Parse()

	var config Config

	if *configFileName != "" {
		jsonFile, err := os.Open(*configFileName)
		byteValue, _ := ioutil.ReadAll(jsonFile)
		err = json.Unmarshal(byteValue, &config)
		if err != nil {
			log.Panic(err)
		}
	} else {
		log.Fatal("Please specify a JSON config file with -c <file.json>")
	}

	tun, tnet, err := netstack.CreateNetTUN(
		[]netip.Addr{config.LocalInternalIP},
		[]netip.Addr{netip.MustParseAddr("8.8.8.8")}, // we don't need DNS?
		1420)
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
