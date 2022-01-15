# Scrimbot

A discord bot for organising 8-man group events using threads. Built for EchoVR Discrod communities.

The bot is written in Python and has a dockerfile included in this repo to easily get it up and running. If you use docker compose an example compose file can be found in examples.

## Configuration
The bot needs two files in ./data

### bot.token
This should be a plain text file containing the bot token.
### config.json
This should be a json file containing the settings for the bot. Settings are on a per-server basis. If you plan to support multiple servers you can add multiple of these blocks. Example below:

```json
{
  "908282497769558036": {
    "scrim_channels": {
      "918571303710101504": {
        "role": 925682196445003786
      }
    },
    "mod_channel": 916220711507472425,
    "mod_role": 925681625017253949,
    "reports_per_day": 2,
    "timeout_role": 926924216853467147,
    "timezone": "Europe/London"
  }
}
```