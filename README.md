# << TITLE >>
<< Short Description >>

## Build Docker image

```bash
  docker build \
    --build-arg APP_IMAGE_VERSION=X.Y.Z \
    --file Dockerfile \
    --tag <<docker-image-name>>:X.Y.Z
    .
```

## Start Docker container

```bash
  docker run --detach \
    --publish 9080:9080 \
    --name <<docker-container-name>> \
    <<docker-image-name>>:X.Y.Z
```

## Stop Docker container

```bash
  docker container stop <<docker-container-name>>
```

## Testing Docker image

```bash
docker build -t open-source-polarion-docker-repo-template:local .
container-structure-test test --image open-source-polarion-docker-repo-template:local --config .config/container-structure-test.yaml
```
