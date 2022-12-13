docker build . && docker run -it --rm -u $(id -u):$(id -g) -v $PWD:/output $(docker build -q .) bash -c "cp wgnc-* /output"
