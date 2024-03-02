https://pypi.org/project/signalbot/
https://github.com/bbernhard/signal-cli-rest-api


# Setup

From above:

## Connect account

mkdir $HOME/.local/share/signal-cli

Start in native mode for setup:
docker run -d --name signal-api -p 127.0.0.1:8080:8080 -v $HOME/.local/share/signal-cli:/home/.local/share/signal-cli -e 'MODE=native' bbernhard/signal-cli-rest-api:0.81

It is possible to set up signal-cli-rest-api as the "real" phone device (needs to use a phone number when setting up). The below command sets it up as linked to an existing phone.

Link the device. "name" sets the name shown in the link list in signal.
http://127.0.0.1:8080/v1/qrcodelink?device_name=box-signal-service


docker stop signal-api
docker rm signal-api

(There is probably a better way to start the container with new arguments.)

## Run service permanently

Start in json-rpc mode for lightweight daemon:
docker run -d --name signal-api --restart=always -p 127.0.0.1:8080:8080 -v $HOME/.local/share/signal-cli:/home/.local/share/signal-cli -e 'MODE=json-rpc' bbernhard/signal-cli-rest-api:0.81

## Stopping and removing

docker stop signal-api
docker rm signal-api