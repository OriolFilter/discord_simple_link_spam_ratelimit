ARG IMAGE="python"
ARG TAG="3.13-alpine"
ARG BASEIMAGE="${IMAGE}:${TAG}"

FROM ${BASEIMAGE}

ARG BUILDDATE
ARG VERSION="1.1"
ARG REPOSITORY="https://github.com/OriolFilter/discord_simple_link_spam_ratelimit"

LABEL "author"="Oriol Filter"
LABEL "version"="${VERSION}"
LABEL "description"="Simple discord bot to handle bots/hacked accounts that will spam links in various channels."
LABEL "repository"="${REPOSITORY}"
LABEL "build_date"="${BUILDDATE}"

ENV VERSION=${VERSION}
ENV BUILDDATE=${BUILDDATE}
ENV REPOSITORY=${REPOSITORY}

ENV DISCORD_API_TOKEN=""
ENV DISCORD_MODERATION_CHANNEL_ID=""
ENV DISCORD_ROLES_TO_PING_ID=""
ENV DISCORD_SERVER_ID=""

RUN apk update --no-cache

WORKDIR /tmp
ADD ./requirements.txt /tmp
RUN pip3 install -r /tmp/requirements.txt

ADD ./entrypoint.sh /entrypoint.sh
ADD ./code /main
WORKDIR /main
RUN chmod +x /main/main.py
CMD ["ash", "/entrypoint.sh"]