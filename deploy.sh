docker buildx build -t ghcr.io/danielkoomen/webapp --push .
docker buildx build -f Dockerfile.nginx -t ghcr.io/danielkoomen/webapp:nginx --push .
