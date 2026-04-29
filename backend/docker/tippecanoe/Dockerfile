FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    build-essential \
    libsqlite3-dev \
    zlib1g-dev \
  && rm -rf /var/lib/apt/lists/*

ARG TIPPECANOE_REPO=https://github.com/felt/tippecanoe.git

WORKDIR /tmp
RUN git clone --depth 1 "${TIPPECANOE_REPO}" tippecanoe

WORKDIR /tmp/tippecanoe
RUN make -j"$(nproc)" \
  && make install \
  && tippecanoe --version \
  && rm -rf /tmp/tippecanoe

ENTRYPOINT ["tippecanoe"]
CMD ["--help"]
