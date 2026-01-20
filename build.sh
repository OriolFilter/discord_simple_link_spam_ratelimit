# docker run --privileged --rm tonistiigi/binfmt --install all

docker buildx build \
--push \
--no-cache \
--platform linux/amd64,linux/arm64/v8 \
--tag oriolfilter/discord_simple_link_spam_ratelimit:v1.1 \
--tag oriolfilter/discord_simple_link_spam_ratelimit:latest .