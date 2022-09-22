# Scrimbot

A discord bot for organising 8-man group events using threads. Built for EchoVR Discord communities.

The bot is written in Python and has a dockerfile included in this repo to easily get it up and running. If you use
docker compose an [example compose file](examples/docker-compose.yaml) can be found in examples.

## Configuration

The bot needs two files in ./data

### bot.token

This should be a plain text file containing the bot token.

## Discord guild/server setup

### Command setup

Go to `Server Settings > Integrations > Bots and Apps > scrimbot > Manage` and set up the slash commands. The following
are some sane suggestions.

#### Everyone/all channels

`/active-scrims`, `/report`, `/oculus-set`, `/oculus-get`, `/time`

#### Everyone/scrim channel(s)

`/ping-scrim`, `/scrim`

#### Moderator role/scrim channel(s)

`/archive-scrim`, `/kick`

#### Moderator role/all channels

`/log`, `/note`, `/warn`, `/purgelog`, `/rmlog`, `/scrim-timeout`

### Server settings

You can use `/settings download` and `/settings upload` to modify the settings for your server. You can find an example
here: [settings file example](examples/settings.json).

The `server` section contains server wide settings, `channel_defaults` are the default settings for each channel.
Under `channel` you can add settings for each specific channel.
