FROM ubuntu:24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/fan-cfd-venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        wget \
        software-properties-common \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        build-essential \
        git \
    && add-apt-repository -y universe \
    && wget -qO /etc/apt/trusted.gpg.d/openfoam.asc https://dl.openfoam.org/gpg.key \
    && add-apt-repository -y http://dl.openfoam.org/ubuntu \
    && apt-get update \
    && apt-get install -y --no-install-recommends openfoam13 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/fan-cfd-requirements.txt

RUN python3 -m venv "${VIRTUAL_ENV}" \
    && pip install --upgrade pip \
    && pip install -r /tmp/fan-cfd-requirements.txt pytest ruff

COPY docker/openfoam-entrypoint.sh /usr/local/bin/openfoam-entrypoint
RUN chmod +x /usr/local/bin/openfoam-entrypoint

WORKDIR /workspace
ENTRYPOINT ["openfoam-entrypoint"]
CMD ["bash"]
