FROM golang:1.17
#8beta2

WORKDIR /code

ADD go.mod /code

RUN go get golang.zx2c4.com/wireguard/device
RUN go get golang.zx2c4.com/go118/netip
RUN go get golang.zx2c4.com/wireguard/tun/netstack

ADD wgnc.go /code

#RUN GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" .
RUN GOOS=android GOARCH=arm64 go build -ldflags="-s -w" .
#RUN go build -ldflags="-s -w" .

CMD ["wgnc"]
