## Discord ollamads bot
[![Made in Ukraine](https://img.shields.io/badge/made_in-ukraine-ffd700.svg?labelColor=0057b7)](https://vshymanskyy.github.io/StandWithUkraine)

A bot to connect to an ollama instance and expose it to discord users. The bot is written in Python and can be run anywhere with a docker container (the instructions on how to do so are below) or you can add the version I host for myself and use that (link below).

The bot has the following features:
- [x] Whitelist for users/channels that can use the bot
- [x] Retain channel context in an internal cache
- [x] Commands for changing the model/settings on a per channel basis
- [x] Show status and loaded model into the ollama instance
- [ ] Help command 

Fell free to contact me on Discord [diminddl](https://discordapp.com/users/312591385624576001) if you have any questions.

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
    "ollama server": "http://host.docker.internal:11434",
    "discord token": "",
    "default prompt": "You are an assistant.",
    "default vision prompt": "You will be ...",
    "vetted users": []
}
```
`ollama server` is the address of the ollama instance you want to connect to, if you want to connect to the instance running on the same computer as the docker leave it at `host.docker.internal`. `discord token` is the discord bot API token you can get from [discord](https://discord.com/developers/). Don't forger to turn on `Privileged Gateway Intents` in the discord bot panel (next to the bot API token). `default prompt` is the default prompt for the model to use. `default vision prompt` is the default prompt for the vision fallback model in case you enable that. 

After that is done hit `ctrl + x`, `y` and `enter`. The settings will be saved.

### Starting the bot 
To start the bot from a stopped state (like we have right now), navigate to it's folder and run the following:
```
sudo docker-compose up -d ollamads
```
You will see it print:
```
Starting ... done
Starting ... done
```
To check the status of the container do `sudo docker container ls` you will see 2 containers `valkey` and `ollamads` that means everything is running.
Now go to the server that you added the bot to and do -help (or whatever command prefix you chose) to see if it's working.
### Debugging
In case you wish to see the console output of the bot, simply run the `sudo docker-compose up` command in the root folder of the bot without the -d argument, the console will stay attached to the bots internal terminal, and in case any errors occur you will see them.

### Stopping
In the folder with the bot run:
```
sudo docker-compose stop
```
