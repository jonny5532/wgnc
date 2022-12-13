FROM golang:1.20rc1

WORKDIR /code

ADD go.mod /code

RUN go get golang.zx2c4.com/wireguard/device
RUN go get golang.zx2c4.com/wireguard/tun/netstack

ADD wgnc.go /code

RUN GOOS=darwin GOARCH=amd64 go build -ldflags="-s -w" -o wgnc-darwin .
RUN GOOS=android GOARCH=arm64 go build -ldflags="-s -w" -o wgnc-android .
RUN go build -ldflags="-s -w" -o wgnc-amd64 .

CMD ["wgnc"]
