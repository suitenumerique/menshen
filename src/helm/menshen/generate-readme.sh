#!/usr/bin/env bash

set -eo pipefail

CHART_DIR="$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if ! docker image ls | grep -q readme-generator-for-helm; then
  git clone https://github.com/bitnami/readme-generator-for-helm.git /tmp/readme-generator-for-helm
  docker build -t readme-generator-for-helm:latest /tmp/readme-generator-for-helm
fi

cd "${CHART_DIR}"
docker run --rm -it -v .:/source -w /source readme-generator-for-helm:latest readme-generator -v values.yaml -r README.md
