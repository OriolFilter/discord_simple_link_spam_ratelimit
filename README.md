# Description

Simple discord bot to handle bots/hacked accounts that will spam links in various channels.

Covers the following scenarios **per user**:

- Total links posted within X seconds
- Total times the same link was posted within X seconds ()
- Attachments are considered individual links, thus covered in the total links clause

## ENV

| ENV                         | Default | Description                                                                                                                                                 | Required                    |
|-----------------------------|---------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------|
| DISCORD_API_TOKEN           | ---     | API token for your bot.                                                                                                                                     | <ul><li>[x] item1</li></ul> |
| DISCORD_MODERATION_ROLES    | ---     | ID of the roles to ping when the moderation is triggered. Multiple IDs are allowed (space separated).  If not specified, it will **ping the server owner**. | <ul><li>[] item1</li></ul>  |
| DISCORD_SERVER_ID           | ---     | ID of the discord server to moderate. Will ignore the messages that don't match the server ID                                                               | <ul><li>[x] item1</li></ul> |
| THRESHOLD_SECONDS           | 3       | Every when to clean up the internal cache/or also named as how wide is the margin.                                                                          | <ul><li>[] item1</li></ul>  |
| THRESHOLD_SAME_LINK_LIMIT   | 5       | Total number of hits (per user and same link) allowed. Triggers when count is above the limit.                                                              | <ul><li>[] item1</li></ul>  |
| THRESHOLD_TOTAL_LINKS_LIMIT | 8       | Total number of total hits/links (per user) allowed. Triggers when count is above the limit.                                                                | <ul><li>[] item1</li></ul>  |

[//]: # (| DISCORD_MODERATION_CHANNEL_ID | If no ID is provided it will post a message for the moderators in the [Public Server Updates Channel]&#40;https://support.discord.com/hc/en-us/articles/360039181052-Public-Server-Updates-Channel&#41; |          |)

## FAQ

### Which permissions does the bot need?

- Read messages
- Read messages history <-- new from v1.1
- Send messages (to the moderation channels too)
- Time Out Members
- Kick Members  <-- new from v1.1
- Ban Members  <-- new from v1.1
- Link embeds  <-- new from v1.1

### Why hardcode the Server ID

This is intended to be hosted in a specific server.

Since I don't have the need of adding this to more than one single server, I haven't bothered to implement more servers.

Let me know if _you_ are intending of using this and I will adjust it.

### Why don't use memcached/redis/valkey/etc

Same as above.

### What about the hardcoded values of the thresholds?

Unless I am aware that someone is intending to use this, for now it will be kept that way.

### Does the reconnect work?

I'm not entirely sure.'

The Liveness Probe in Kubernetes works well to restart the container whenever something goes wrong, so the container gets restarted/recreated and attempts to connect.

### Which is the latest docker image?

```
oriolfilter/discord_simple_link_spam_ratelimit:latest
```

## Building

Multi-platform build

```shell
$ ./build.sh
```

```text
[+] Building 0.0s (0/0)                                                                                                                                                                                           docker:default
ERROR: failed to build: Multi-platform build is not supported for the docker driver.
Switch to a different driver, or turn on the containerd image store, and try again.
Learn more at https://docs.docker.com/go/build-multi-platform/
```

Install QUEMU

```shell
docker run --privileged --rm tonistiigi/binfmt --install all
```

```shell
docker buildx ls
```

```text

NAME/NODE     DRIVER/ENDPOINT   STATUS    BUILDKIT   PLATFORMS
default*      docker                                 
 \_ default    \_ default       running   v0.23.2    linux/amd64 (+3), linux/arm64, linux/arm (+2), linux/ppc64le, (6 more)
```

Create a builder instance for each platform

```shell
docker buildx create --name mybuilder --use
```

Then try to build again.

For more info refer to the [official Docker documentation for building multi-platform builds.](https://docs.docker.com/build/building/multi-platform/#qemu) 

## Running

### Docker

```yaml
services:
  discord_bot:
    image: oriolfilter/discord_simple_link_spam_ratelimit:latest
    container_name: discord_spam_bot
    restart: always
    environment:
      DISCORD_API_TOKEN: "000111222333"
      DISCORD_MODERATION_ROLES: "43214321 89894848" 
      DISCORD_SERVER_ID: "9898989898"
```

### Kubernetes

Please don't use environment vars, this is just an example.

Secrets are good.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: spam-discord-bot
  labels:
    app: spam-discord-bot
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: spam-discord-bot
  template:
    metadata:
      labels:
        app: spam-discord-bot
    spec:
      terminationGracePeriodSeconds: 5
      containers:
        - name: spam-discord-bot
          image: oriolfilter/discord_simple_link_spam_ratelimit:latest
          securityContext:
            runAsUser: 1000
            runAsGroup: 1000
            allowPrivilegeEscalation: false
          readinessProbe:
            exec:
              command:
                - cat
                - /tmp/healthy
            initialDelaySeconds: 7
            failureThreshold: 3
            periodSeconds: 5
          livenessProbe:
            exec:
              command:
                - cat /tmp/healthy
            initialDelaySeconds: 7
            failureThreshold: 3
            periodSeconds: 5
          imagePullPolicy: Always
          env:
            - name: TZ
              value: 'Europe/Madrid'
            - name: DISCORD_API_TOKEN
              value: "000011112222334444555"
            - name: DISCORD_MODERATION_ROLES
              value: '2222222 33333 44444'
            - name: DISCORD_SERVER_ID
              value: '111111111'
```