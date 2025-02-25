## Discord ollamads bot
[![Made in Ukraine](https://img.shields.io/badge/made_in-ukraine-ffd700.svg?labelColor=0057b7)](https://vshymanskyy.github.io/StandWithUkraine)

A bot to connect to an ollama instance and expose it to discord users. The bot is written in Python and can be run anywhere with a docker container (the instructions on how to do so are below) or you can add the version I host for myself and use that (link below).

The bot has the following features:
- [ ] Whitelist for users/channels that can use the bot
- [ ] Retain channel context in an internal cache
- [ ] Commands for changing the model/settings on a per channel basis
- [ ] Show status and loaded model into the ollama instance
- [ ] Help command 

Fell free to contact me on Discord [diminddl](https://discordapp.com/users/312591385624576001) if you have any questions.

# Add the bot to your server
If you don't want to host it yourself you can just invite the public version using this invite TODO.

## Installation and first run
The following instructions will be for a Debian system.
(It is recommended that you [add yourself](https://docs.docker.com/engine/install/linux-postinstall/) to the docker user group to omit sudo from the docker commands)
### Install docker:

https://docs.docker.com/engine/install/debian/

### Clone the repository
```
git clone https://github.com/diminDDL/discord-ollama
```
### Navigate to installed folder and start the docker container
**⚠️ Depending on your version of docker compose you will either need to use `docker-compose` or `docker compose` to run this correctly.**
```
cd discord-ollama
sudo docker-compose up
```
Docker will download all dependencies and start. This can take a while.
After it finishes starting hit `ctrl+c` to stop it and wait until it finishes.

### Set API keys
```
nano ./data/init_settings.json
```
This will open nano editor where you will see something like this:
```
{
    "ollama server": "http://localhost:11434",
    "discord token": "",
    "prefix": "-",
}
```
`ollama server` is the address of the ollama instance you want to connect to. `discord token` is the discord bot API token you can get from [discord](https://discord.com/developers/). `prefix` is what the bot will use as a command prefix for example `-` or `ex` or any other string or character. Don't forger to turn on `Privileged Gateway Intents` in the discord bot panel (next to the bot API token).

After that is done hit `ctrl + x`, `y` and `enter`. The settings will be saved.

### Starting the bot 
To start the bot from a stopped state (like we have right now), navigate to it's folder (discordPiLocator) and run the following:
```
sudo docker-compose up -d ollamads
```
You will see it print:
```
Starting redis ... done

Starting ... done
```
To check the status of the container do `sudo docker container ls` you will see 2 containers `valkey` and `ollamads` that means everything is running.
Now go to the server that you added the bot to and do -help (or whatever command prefix you chose) to see if it's working.
### Stopping
In the folder with the bot run:
```
sudo docker-compose stop
```
