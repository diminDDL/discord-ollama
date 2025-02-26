#  Copyright (c) 2025 diminDDL, Cuprum77
#  License: MIT License

import os
from datetime import datetime
from pathlib import Path

import aiohttp
import psutil
import discord
import redis.asyncio as redis
import json
import asyncio
from ollama import AsyncClient
from discord.ext import commands, bridge


__name__ = "ollamads"
__version__ = "1.0"
__author__ = "diminDDL and Cuprum"

extensions = [
    "sudocog",
    "chatcog",
    "utilitiescog",
    "listenercog",
]

tempdir = "/tmp/ollamads/"
datadir = "/app/data"
dirname = "/app/ollamads"

# this is a pretty dumb way of doing things, but it works
intents = discord.Intents.all()

# check if the init_settings.json file exists and if not, create it
if not Path(os.path.join(datadir, "init_settings.json")).exists():
    print("No init_settings.json file found. Creating one now.")

    settings_dict_empty = {
        "ollama server": "http://host.docker.internal:11434",
        "discord token": "",
        "default prompt": "What do you want to say?",
        "vetted users": [],
    }

    with open(os.path.join(datadir, "init_settings.json"), "w") as f:
        json.dump(settings_dict_empty, f, indent=4, ensure_ascii=False)
    os.chown(os.path.join(datadir, "init_settings.json"), 1000, 1000)

    exit(1)

# load the init_settings.json file with the json library
with open(os.path.join(datadir, "init_settings.json"), "r") as f:
    try:
        settings_dict = json.load(f)
        # get the discord token, the tenor api key, and the prefix from the dict
        ollama_server_url = settings_dict["ollama server"]
        discord_token = settings_dict["discord token"]
        default_prompt = settings_dict["default prompt"]
        vetted_users = [int(user) for user in settings_dict["vetted users"]]

    except json.decoder.JSONDecodeError:
        print("init_settings.json is not valid json. Please fix it.")
        exit(1)


# define the bot class
class ollamads(bridge.Bot):
    def __init__(self, dirname, help_command=None, description=None, **options):
        super().__init__(help_command=help_command, description=description, **options)
        # ---static values---
        self.ollama_server = ollama_server_url
        self.default_prompt = default_prompt
        self.vetted_users = vetted_users
        # paths
        self.dirname = dirname
        self.datadir = "/app/data/"
        self.tempdir = "/tmp/"

        # info
        self.version = __version__
        self.starttime = datetime.now()
        self.pid = os.getpid()
        self.process = psutil.Process(os.getpid())

        # ---dynamic values---

        # settings
        self.debugmode = False
        # sessions
        self.aiohttp_session = None  # give the aiohttp session an initial value
        self.loop.run_until_complete(self.aiohttp_start())

        print("Connecting to redis...")
        try:
            self.redis = redis.Redis(host="ollamads_redis", db=1, decode_responses=True)
            print("Connection successful.")
        except redis.ConnectionError:
            print("Redis connection failed. Check if redis is running.")
            exit(1)

        # ollama connection
        self.ollama = AsyncClient(host=self.ollama_server)
        # model_list = self.loop.run_until_complete(self.ollama.list())
        # print(f"Connected to ollama server at {self.ollama_server}. Models: {model_list}")

        # bot status info
        self.cpu_usage = 0
        self.command_invokes_hour = 0
        self.command_invokes_total = 0

        # whitelists
        # Whitelist means that guilds have to be whitelisted by the bot owner to use the bot
        # Whitelist means that channels have to be whitelisted by the owner of the guild to use the bot
        # Whitelist means that users have to be whitelisted by the owner of the guild to use the bot
        # Blacklist is the opposite of whitelist
        # True = whitelist, False = blacklist
        self.guilds_mode = True         # By default bot owner whitelists guilds
        self.listed_guilds = []
    
        self.guild_lists = {
            "modes": {
                "channels": True,
                "users": False
            },
            "lists": {
                "channels": [],
                "users": []
            }
        }

        # try to load the guild_mode and listed_guilds from the redis database
        try:
            self.loop.run_until_complete(self.fetch_redis())
        except redis.exceptions.ConnectionError:
            print("Redis connection failed. Check if redis is running.")
            exit(1)


    async def fetch_redis(self):
        self.guilds_mode = bool(await self.redis.get("guilds_mode"))
        self.listed_guilds = await self.redis.smembers("listed_guilds")
        self.guild_lists = await self.redis.hgetall("guild_lists")


    async def aiohttp_start(self):
        self.aiohttp_session = aiohttp.ClientSession()


# create the bot instance
print(f"Starting ollamads v {__version__} ...")
bot = ollamads(dirname, intents=intents)
print(f"Loading {len(extensions)} extensions: \n")

# load the cogs aka extensions
for ext in extensions:
    try:
        print(f"   loading {ext}")
        bot.load_extension(f'ollamads.cogs.{ext}')
    except Exception as exc:
        print(f"error loading {ext}")
        raise exc

# try to start the bot with the token from the init_settings.json file catch any login errors
try:
    bot.run(discord_token)
except discord.LoginFailure:
    print("Login failed. Check your token. If you don't have a token, get one from https://discordapp.com/developers/applications/me")
    exit(1)


