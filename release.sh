#!/usr/bin/env bash
# Publishes a new image version to GHCR. A published tag is never overwritten.
# Usage: ./release.sh v2        (DOCKER=podman ./release.sh v2 to use podman)
set -euo pipefail
VERSION="${1:?usage: ./release.sh vN}"
REPO="two2bac-git/plow-agent"
IMAGE="ghcr.io/$REPO"
DOCKER="${DOCKER:-docker}"
cd "$(dirname "$0")"

git diff --quiet HEAD -- || { echo "Commit first: the image records the commit it was built from." >&2; exit 1; }
git fetch -q
[ "$(git rev-parse HEAD)" = "$(git rev-parse '@{u}')" ] || { echo "Push first: the image's commit must be on GitHub." >&2; exit 1; }

registry_digest() {  # anonymous read, so it also proves the package is public
  local token
  token=$(curl -fsS "https://ghcr.io/token?scope=repository:$REPO:pull" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')
  curl -sI -H "Authorization: Bearer $token" \
    -H "Accept: application/vnd.docker.distribution.manifest.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.oci.image.index.v1+json" \
    "https://ghcr.io/v2/$REPO/manifests/$1" | tr -d '\r' | awk -F': ' 'tolower($1)=="docker-content-digest"{print $2}'
}

[ -z "$(registry_digest "$VERSION")" ] || { echo "$IMAGE:$VERSION already exists; pick a new version." >&2; exit 1; }

# --no-cache: a cached build silently kept VERSION=dev / REVISION=unknown in v4 and v5
BUILDAH_FORMAT=docker "$DOCKER" build --no-cache \
  --build-arg VERSION="$VERSION" --build-arg REVISION="$(git rev-parse HEAD)" -t "$IMAGE:$VERSION" .
"$DOCKER" push "$IMAGE:$VERSION"

digest=$(registry_digest "$VERSION")
[ -n "$digest" ] || { echo "Pushed, but GHCR does not serve $VERSION anonymously: make the package public." >&2; exit 1; }
echo "Published: $IMAGE@$digest"
echo "Once Plow has admitted the image: plow-agents image promote plow-agent $IMAGE@$digest"
