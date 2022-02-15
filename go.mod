module github.com/jonny5532/wgnc

go 1.17

replace (
    golang.zx2c4.com/wireguard/tun/netstack => github.com/jonny5532/wireguard-go/tun/netstack eb7c63b485b783a8e6262ac923d8f3a5c89917c8
    golang.zx2c4.com/wireguard => github.com/jonny5532/wireguard-go eb7c63b485b783a8e6262ac923d8f3a5c89917c8
)
