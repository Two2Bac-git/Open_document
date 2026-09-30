# Open to CC: a variant of Plow's OpenClaw base image (persona + skills + plow.py).
# Pinned by digest: the base boots holding this agent's Plow credential. To bump, take a
# newer base-<sha> tag and its digest from https://gallery.ecr.aws/e1h7x4a2/plow-cloud-agents
ARG BASE_IMAGE=public.ecr.aws/e1h7x4a2/plow-cloud-agents:base-771198a9609dcef54d44843e7da5329c17fa51b4@sha256:f1e7c421b97a80f1bd17015f96daceb965f350a241f7edc7e4d856a0e3a6f8f5

# The image only exists if the self-check passes (on the base's own python3).
FROM ${BASE_IMAGE} AS check
COPY plow.py indexer.py report.py agent_index_client.py test_plow.py /tmp/check/
RUN cd /tmp/check && PYTHONDONTWRITEBYTECODE=1 python3 test_plow.py >/dev/null

FROM ${BASE_IMAGE}
ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="Open to CC" \
      org.opencontainers.image.description="Plow agent that sorts a folder on the owner's computer by file type and repairs broken shortcuts, never reading file content." \
      org.opencontainers.image.source="https://github.com/Two2Bac-git/Open_document" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.authors="Andrey Bacelar" \
      org.opencontainers.image.version=$VERSION \
      org.opencontainers.image.revision=$REVISION
# Agent Index identity: a cloud install runs the image with no compose file, so these
# are the only place the id and page come from. The base registers and reports usage.
ENV AGENT_ID=plow-agent \
    AGENT_NAME="Open to CC" \
    AGENT_BLURB="A 100% customizable repo within the rules of the game ;) Your folders end up the way that best defines your directory, without breaking symlinks. Updates from me and from others are welcome, with care: Andrey Bacelar" \
    PLOW_THREAD_TRUST=untrusted
# untrusted: new groups are plain chats, so nobody in a group gets the owner's Mac by default.
COPY prompt/AGENTS.md /opt/plow/prompt/AGENTS.md
COPY skills/ /opt/plow/skills/
COPY --from=check /tmp/check/plow.py /opt/plow/skills/open-to-cc/scripts/plow.py
