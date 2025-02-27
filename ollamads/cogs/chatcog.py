#  Copyright (c) 2025 diminDDL, Cuprum77
#  License: MIT License

from re import T
import discord
import asyncio
import json
import io
import base64
import aiohttp
import tempfile
import datetime
from enum import IntEnum
from typing import List, Dict
from datetime import datetime
from discord.ext import commands
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ProcessPoolExecutor
from ollama import AsyncClient


class ChatAdminCommandsEnum(IntEnum):
    """Commands available for chat admin"""
    ban = 0
    unban = 1
    server_ban = 2
    server_unban = 3
    user_history = 4
    ban_status = 5
    whitelist_add = 6
    whitelist_rm = 7


class ChatConfigCommandsEnum(IntEnum):
    """Commands available for chat config"""
    reload = 0
    list = 1
    set = 2
    get = 3
    prompt = 4
    bot2bot = 5
    clear = 6
    status = 7
    whitelist = 8
    whitelist_ls = 9


class ChatUserCommandsEnum(IntEnum):
    """Commands available for chat user"""
    clear = 0
    history = 1
    banned = 2


class BanObject:
    def __init__(self, user_id: int, reason: str, timestamp: str, issuer_id: int, channels: list, server_ban: bool = False):
        self.user_id = user_id
        self.reason = reason
        self.timestamp = datetime.fromisoformat(timestamp) if timestamp else None
        self.issuer_id = issuer_id
        self.channels = channels
        self.server_ban = server_ban

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "issuer_id": self.issuer_id,
            "channels": self.channels,
            "server_ban": self.server_ban
        }


class ChatCommands(commands.Cog):
    """
    This cog is used to allow users to chat with the model.
    """
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.default_prompt = self.bot.default_prompt
        self.vetted_users = self.bot.vetted_users
        self.redis = self.bot.redis
        self.ollama = self.bot.ollama
        self.pp = ProcessPoolExecutor(max_workers=1)    
        self.sep = asyncio.Semaphore(2)
        self.ll = asyncio.get_event_loop()     
        self.max_history = 20   
        
        bot.loop.create_task(self.__load_models_async__())


    @commands.guild_only()
    @commands.slash_command(name="admin")
    async def chat_admin_cmd(self, ctx: discord.ApplicationContext, command: ChatAdminCommandsEnum, user: discord.Member, reason: str = ""):
        """
        This command is used to manage user permissions for the bot.
        """
        if ctx.author.id not in self.vetted_users:
            return await ctx.respond("You are not authorized to use this command.", ephemeral=True)

        match command:
            case ChatAdminCommandsEnum.ban:
                await self.__ban__(ctx, user, reason)
            case ChatAdminCommandsEnum.unban:
                await self.__unban__(ctx, user)
            case ChatAdminCommandsEnum.server_ban:
                await self.__server_ban__(ctx, user, reason)
            case ChatAdminCommandsEnum.server_unban:
                await self.__server_unban__(ctx, user)
            case ChatAdminCommandsEnum.ban_status:
                await self.__ban_status__(ctx, user)
            case ChatAdminCommandsEnum.user_history:
                await self.__history__(ctx, user.id)
            case ChatAdminCommandsEnum.whitelist_add:
                await self.__whitelist_add__(ctx, user)
            case ChatAdminCommandsEnum.whitelist_rm:
                await self.__whitelist_rm__(ctx, user)
            case _:
                await ctx.respond("Invalid command.")


    @commands.guild_only()
    @commands.slash_command(name="config")
    async def chat_config_cmd(self, ctx: discord.ApplicationContext, command: ChatConfigCommandsEnum, argument: str = ""):
        """
        This command is used to manage the chat settings for the bot.
        """
        if ctx.author.id not in self.vetted_users:
            return await ctx.respond("You are not authorized to use this command.", ephemeral=True)

        match command:
            case ChatConfigCommandsEnum.reload:
                await self.__reload__(ctx)
            case ChatConfigCommandsEnum.list:
                await self.__list__(ctx)
            case ChatConfigCommandsEnum.set:
                await self.__set__(ctx, argument)
            case ChatConfigCommandsEnum.get:
                await self.__get__(ctx)
            case ChatConfigCommandsEnum.prompt:
                await self.__prompt__(ctx, argument)
            case ChatConfigCommandsEnum.bot2bot:
                await self.__bot2bot__(ctx)
            case ChatConfigCommandsEnum.clear:
                await self.__admin_clear__(ctx)
            case ChatConfigCommandsEnum.status:
                await self.__status__(ctx)
            case ChatConfigCommandsEnum.whitelist:
                await self.__whitelist__(ctx)
            case ChatConfigCommandsEnum.whitelist_ls:
                await self.__whitelist_ls__(ctx)
            case _:
                await ctx.respond("Invalid command.")


    @commands.guild_only()
    @commands.slash_command(name="chat")
    async def chat_user_cmd(self, ctx: discord.ApplicationContext, command: ChatUserCommandsEnum):
        """
        This command is used to chat with the bot.
        """
        match command:
            case ChatUserCommandsEnum.clear:
                await self.__clear__(ctx)
            case ChatUserCommandsEnum.history:
                await self.__history__(ctx, ctx.author.id)
            case ChatUserCommandsEnum.banned:
                await self.__user_ban_status__(ctx)
            case _:
                await ctx.respond("Invalid command.")


    async def __get_ban_object__(self, redis_key: str, user: discord.Member):
        """
        Get the ban object for a specific user. Returns None if the user is not banned.
        """
        user_obj = None

        if await self.redis.exists(redis_key):
            user_obj = await self.redis.hget(redis_key, user.id)
            if user_obj:
                try:
                    user_obj = json.loads(user_obj)
                    user_obj = BanObject(**user_obj)
                except json.JSONDecodeError:
                    user_obj = None

        return user_obj
    

    async def __create_ban_object__(self, redis_key: str, user: discord.Member, reason: str, channels: list, issuer_id: int, server_ban: bool = False, create_new: bool = False):
        """
        Get the ban object for a specific user. Returns a new object if the user is not banned.
        """
        user_obj = None

        if not user_obj or create_new:
            user_obj = BanObject(
                user_id = user.id,
                reason = reason,
                timestamp = datetime.now().isoformat(),
                issuer_id = issuer_id,
                channels = channels,
                server_ban = server_ban
            )
        else:
            user_obj = await self.__get_ban_object__(redis_key, user)
            user_obj.reason = reason
            user_obj.timestamp = datetime.now().isoformat()
            user_obj.issuer_id = issuer_id
            for channel in channels:
                if channel not in user_obj.channels:
                    user_obj.channels.append(channel)
                    
            user_obj.server_ban = server_ban

        return user_obj


    async def __ban__(self, ctx: discord.ApplicationContext, user: discord.Member, reason: str = ""):
        """
        Ban a user from using the bot.
        """
        redis_key = f"guild:{ctx.guild.id}:admin"
        user_obj = await self.__create_ban_object__(redis_key, user, reason, [ctx.channel.id], ctx.author.id)

        if not user_obj:
            return await ctx.respond("User is already banned in this channel.", ephemeral=True)
        if user_obj.server_ban:
            return await ctx.respond("User is banned in the entire server.", ephemeral=True)

        await self.redis.hset(redis_key, user_obj.user_id, json.dumps(user_obj.to_dict()))
        await ctx.respond(f"{user.mention} is now banned from using {self.bot.user.mention} in {ctx.channel.mention}.")


    async def __unban__(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Unban a user from using the bot.
        """
        redis_key = f"guild:{ctx.guild.id}:admin"
        user_obj = await self.__get_ban_object__(redis_key, user)

        if not user_obj:
            return await ctx.respond("User is not banned.", ephemeral=True)
        if user_obj.server_ban:
            return await ctx.respond("User is banned in the entire server.", ephemeral=True)
        
        # if its the only channel, remove the ban object from redis
        if len(user_obj.channels) == 1 and user_obj.channels[0] == ctx.channel.id:
            await self.redis.hdel(redis_key, user.id)
        else:
            # delete all the channels that match the current channel
            user_obj.channels = [channel for channel in user_obj.channels if channel != ctx.channel.id]                
            await self.redis.hset(redis_key, user.id, json.dumps(user_obj.to_dict()))
            
        await ctx.respond(f"{user.mention} is now unbanned from using {self.bot.user.mention} in {ctx.channel.mention}.")


    async def __server_ban__(self, ctx: discord.ApplicationContext, user: discord.Member, reason: str):
        """
        Ban a user from using the bot in the entire server. Overrides any regular channel bans.
        """
        redis_key = f"guild:{ctx.guild.id}:admin"
        user_obj = await self.__create_ban_object__(redis_key, user, reason, None, ctx.author.id, server_ban=True, create_new=True)

        if not user_obj:
            return await ctx.respond("User is already banned in this server.")
        if user_obj.server_ban:
            return await ctx.respond("User is already banned in the entire server.", ephemeral=True)

        await self.redis.hset(redis_key, user_obj.user_id, json.dumps(user_obj.to_dict()))
        await ctx.respond(f"{user.mention} is now banned from using {self.bot.user.mention} in ***{ctx.guild.name}***.")


    async def __server_unban__(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Unban a user from using the bot in the entire server. Overrides any regular channel bans.
        """
        redis_key = f"guild:{ctx.guild.id}:admin"
        user_obj = await self.__get_ban_object__(redis_key, user)

        if not user_obj:
            return await ctx.respond("User is not banned.", ephemeral=True)
        
        # remove the ban object from redis
        await self.redis.hdel(redis_key, user.id)
        await ctx.respond(f"{user.mention} is now unbanned from using {self.bot.user.mention} in ***{ctx.guild.name}***.")


    async def __history__(self, ctx: discord.ApplicationContext, user: str):
        """
        Get the chat history for a specific user. Requires user ID.
        """
        if not user:
            return await ctx.respond("Please provide a user ID.", ephemeral=True)
        
        # try to get the id from a mention
        try:
            user = int(user)
        except:
            return await ctx.respond("Invalid user ID.", ephemeral=True)

        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:user:{user}:history"
        chat_history = await self.redis.hget(redis_key, "chat_history")

        if not chat_history:
            return await ctx.respond("No chat history found for this user.", ephemeral=True)

        chat_history = json.loads(chat_history)
        # remove the first entry which is the system prompt
        chat_history.pop(0)
        chat_history = json.dumps(chat_history, indent=4)

        # create a temporary file to send the chat history
        with tempfile.NamedTemporaryFile(mode="w", delete=False, newline="\n", suffix=".json") as f:
            f.write(chat_history)
            temp_filename = f.name

        await ctx.respond(file=discord.File(temp_filename))


    async def __ban_status__(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Get the ban status for a specific user.
        """
        redis_key = f"guild:{ctx.guild.id}:admin"
        user_obj = await self.__get_ban_object__(redis_key, user)

        if not user_obj:
            return await ctx.respond(f"{user.mention} is not banned.", ephemeral=True)
                        
        # create embed
        embed = discord.Embed(
            title="Ban Status",
            color=discord.Color.red(),
            timestamp=user_obj.timestamp
        )

        embed.add_field(
            name="User",
            value=user.mention,
            inline=False
        )

        reason = user_obj.reason if user_obj.reason else "No reason provided."
        embed.add_field(
            name="Reason",
            value=reason,
            inline=False
        )

        embed.add_field(
            name="Server Ban",
            value="Yes",
            inline=False
        )

        if not user_obj.server_ban:
            embed.add_field(
                name="Banned Channels",
                value=", ".join([f"<#{channel}>" for channel in user_obj.channels]),
                inline=False
            )

        # add issuer in the footer
        issuer = ctx.guild.get_member(user_obj.issuer_id)
        if issuer:
            embed.set_footer(text=f"Issued by {issuer.name}")

        await ctx.respond(embed=embed)


    async def __user_ban_status__(self, ctx: discord.ApplicationContext):
        """
        Check if you are banned from using the bot.
        """
        redis_key = f"guild:{ctx.guild.id}:admin"
        user_obj = await self.__get_ban_object__(redis_key, ctx.author)

        if not user_obj:
            return await ctx.respond(f"You are not banned.", ephemeral=True)
        
        issuer = ctx.guild.get_member(user_obj.issuer_id)
        if issuer:
            issuer = issuer.mention
        else:
            issuer = "Unknown"
        
        return await ctx.respond(f"You are banned in {ctx.channel.mention} by {issuer}. (Reason: {user_obj.reason})", ephemeral=True)
    

    async def __whitelist_add__(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Add a user to the whitelist.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        whitelist = await self.redis.hget(redis_key, "whitelist")

        if whitelist == "False":
            return await ctx.respond("Whitelist is disabled.", ephemeral=True)

        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:whitelist"
        if await self.redis.sismember(redis_key, user.id):
            return await ctx.respond(f"{user.mention} is already in the whitelist.", ephemeral=True)
        
        await self.redis.sadd(redis_key, user.id)
        await ctx.respond(f"{user.mention} is now added to the whitelist.")


    async def __whitelist_rm__(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Remove a user from the whitelist.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        whitelist = await self.redis.hget(redis_key, "whitelist")

        if whitelist == "False":
            return await ctx.respond("Whitelist is disabled.", ephemeral=True)

        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:whitelist"
        if not await self.redis.sismember(redis_key, user.id):
            return await ctx.respond(f"{user.mention} is not in the whitelist.", ephemeral=True)
        
        await self.redis.srem(redis_key, user.id)
        await ctx.respond(f"{user.mention} is now removed from the whitelist.")


    async def __whitelist_ls__(self, ctx: discord.ApplicationContext):
        """
        List the users in the whitelist.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        whitelist = await self.redis.hget(redis_key, "whitelist")

        if whitelist == "False":
            return await ctx.respond("Whitelist is disabled.", ephemeral=True)

        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:whitelist"
        whitelist = await self.redis.smembers(redis_key)

        if not whitelist:
            return await ctx.respond("No users are in the whitelist.", ephemeral=True)
        
        whitelist = [ctx.guild.get_member(int(user)).mention for user in whitelist]

        embed = discord.Embed(
            title="Whitelist",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="Users",
            value=", ".join(whitelist),
            inline=False
        )

        await ctx.respond(embed=embed)


    async def __reload__(self, ctx: discord.ApplicationContext):
        """
        This command is used to reload the model list.
        """
        await self.__load_models_async__()
        await ctx.respond("Model list reloaded.")


    async def __list__(self, ctx: discord.ApplicationContext):
        """
        This command is used to list the available models.
        """
        await ctx.respond(embed=self.__format_model_list__(self.models), ephemeral=True)
    

    async def __set__(self, ctx: discord.ApplicationContext, model = ''):
        """
        This command is used to select a model for a specific channel. Requires model name.
        """
        if not model:
            return await ctx.respond("Please provide a model name.", ephemeral=True)

        model = model.lower().strip()

        # Ensure `self.models` is populated before checking
        if not self.models:
            return await ctx.respond("No models are available at the moment. Please try again later.")

        valid_models = {m["model"].lower(): m["model"] for m in self.models}  # Preserve original names

        if model not in valid_models:
            return await ctx.respond(
                f"Invalid model name. Available models: {', '.join(valid_models.values())}"
            )

        # Improved Redis key structure
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        await self.redis.hset(redis_key, "model", valid_models[model])

        await ctx.respond(f"Model set to **{valid_models[model]}**")


    async def __get__(self, ctx: discord.ApplicationContext):
        """
        This command is used to get the selected model for a specific channel.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        model = await self.redis.hget(redis_key, "model")

        if not model:
            return await ctx.respond("No model selected for this channel.")

        await ctx.respond(f"Model selected for this channel: **{model}**")


    async def __prompt__(self, ctx: discord.ApplicationContext, message: str = ""):
        """
        Get or Set the system prompt for the model, for this specific channel.
        """
        if message is None or message == "":
            redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
            prompt = await self.redis.hget(redis_key, "prompt")

            if not prompt:
                prompt = self.default_prompt
                await self.redis.hset(redis_key, "prompt", prompt)

            await ctx.respond(f"Current prompt: ```{prompt}```")

        else:
            redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
            await self.redis.hset(redis_key, "prompt", message)
            await ctx.respond(f"Prompt set to: ```{message}```")


    async def __bot2bot__(self, ctx: discord.ApplicationContext):
        """
        This command is used to enable or disable bot-to-bot communication.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        bot2bot = await self.redis.hget(redis_key, "bot2bot")
        
        if bot2bot == "True":
            bot2bot = "False"
        else:
            bot2bot = "True"

        await self.redis.hset(redis_key, "bot2bot", bot2bot)
        await ctx.respond(f"Bot2Bot communication is now {'enabled' if bot2bot == "True" else 'disabled'}.")


    async def __admin_clear__(self, ctx: discord.ApplicationContext):
        """
        Clear the chat history for this channel.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:user:*:history"
        keys = []
        async for key in self.redis.scan_iter(redis_key):
            keys.append(key)

        for key in keys:
            await self.redis.hdel(key, "chat_history")

        await ctx.respond("The entire chat history is cleared for this channel.")


    async def __status__(self, ctx: discord.ApplicationContext):
        """
        Get the status of the bot.
        """
        
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        model = await self.redis.hget(redis_key, "model")
        bot2bot = await self.redis.hget(redis_key, "bot2bot")
        
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:user:*:history"
        keys = {}
        async for key in self.redis.scan_iter(redis_key):
            user_id = int(key.split(":")[5])
            keys[user_id] = key
            
        # get the length of the chat history from each user
        chat_history = {}
        for user_id, key in keys.items():
            chat_history[user_id] = await self.redis.hget(key, "chat_history")
            if chat_history[user_id]:
                chat_history[user_id] = json.loads(chat_history[user_id])
            else:
                chat_history[user_id] = None

        # build the chat history
        history = ""
        for user_id, user_history in chat_history.items():
            length = len(user_history) if user_history else 0
            # hide the system prompt
            if length > 0:
                length - 1
            history += f"<@{user_id}> has {len(user_history)} entries (max {self.max_history})\n"
                
        # build an embed
        embed = discord.Embed(
            title="Bot Status",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )

        embed.add_field(
            name="Model",
            value=model if model else "Not set",
            inline=False
        )

        embed.add_field(
            name="Bot2Bot",
            value=bot2bot if bot2bot else "Not set",
            inline=False
        )

        embed.add_field(
            name="Chat History",
            value=history if history else "No chat history yet!",
            inline=False
        )

        await ctx.respond(embed=embed)


    async def __whitelist__(self, ctx: discord.ApplicationContext):
        """
        Enable or disable the whitelist for the bot.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        whitelist = await self.redis.hget(redis_key, "whitelist")

        if whitelist == "True":
            whitelist = "False"
        else:
            whitelist = "True"

        await self.redis.hset(redis_key, "whitelist", whitelist)
        await ctx.respond(f"Whitelist is now {'enabled' if whitelist == 'True' else 'disabled'}.")
        

    async def __clear__(self, ctx: discord.ApplicationContext):
        """
        Clear your chat history for this channel.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:user:{ctx.author.id}:history"
        await self.redis.hdel(redis_key, "chat_history")
        await ctx.respond("Chat history cleared.", ephemeral=True)
        

    async def __check_ban_or_whitelist__(self, ctx: discord.ApplicationContext, user: discord.Member):
        """
        Check if a user is banned from using the bot.
        """
        redis_user_key = f"guild:{ctx.guild.id}:admin"
        user_obj = await self.__get_ban_object__(redis_user_key, user)

        if user_obj:
            if user_obj.server_ban:
                return True
            
            if ctx.channel.id in user_obj.channels:                
                return True
            
        redis_whitelist_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        whitelist = await self.redis.hget(redis_whitelist_key, "whitelist")

        if whitelist == "True":
            redis_channel_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:whitelist"
            if not await self.redis.sismember(redis_channel_key, user.id):
                return True
            
        return False


    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Listen for messages and respond to mentions.
        """
        ctx = await self.bot.get_context(message)

        if not message.guild:
            return
        
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        allow_bots = await self.redis.hget(redis_key, "bot2bot")

        if message.author.bot and (allow_bots == "False"):
            return
        elif message.author == self.bot.user:
            return
        
        if message.content == "":
            return
        
        message_content = message.content

        image_url_list = []
        image_url = None
        
        if message.attachments:
            for attachment in message.attachments:
                image_url_list.append(attachment.url)

        if image_url_list:
            image_url = image_url_list[0]

        if message.reference and message.reference.message_id: 
            if await self.__check_ban_or_whitelist__(ctx, message.author):
                return

            referenced_message = await message.channel.fetch_message(message.reference.message_id)
            # Suggested by https://github.com/R2Boyo25
            message_content = "> " + referenced_message.content.strip().replace("\n", "\n> ")

            if referenced_message.author != self.bot.user:
                if referenced_message.attachments:
                    for attachment in referenced_message.attachments:
                        image_url_list.append(attachment.url)

            if image_url_list:
                image_url = image_url_list[0]

            if (referenced_message.author == self.bot.user) or (self.bot.user in message.mentions):
                await self.__llm_chat__(ctx, message_content, image_url)

        elif self.bot.user in message.mentions:
            if await self.__check_ban_or_whitelist__(ctx, message.author):
                return
            
            await self.__llm_chat__(ctx, message_content, image_url)


    async def __image_to_base64__(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return base64.b64encode(await response.read()).decode("utf-8")
                
        return None


    async def __llm_chat__(self, ctx: discord.ApplicationContext, message: str, image_url: str = None):
        """
        Chat with the selected model using an image.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        redis_key_history = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:user:{ctx.author.id}:history"
        model = await self.redis.hget(redis_key, "model")

        if not model:
            return await ctx.respond("No model selected for this channel.")
        
        prompt = await self.redis.hget(redis_key, "prompt")

        if not prompt:
            prompt = self.default_prompt
            await self.redis.hset(redis_key, "prompt", prompt)

        try:
            async with ctx.typing():
                # Get chat history from redis
                chat_history = await self.redis.hget(redis_key_history, "chat_history")

                if chat_history:
                    chat_history = json.loads(chat_history)
                else:
                    chat_history = None

                # Fetch image from URL and save to file, if provided
                image_base64 = []
                if image_url:
                    image_base64.append(await self.__image_to_base64__(image_url))
                else:
                    image_base64 = None

                if chat_history is None:
                    chat_history = [
                        {
                            "role": "system",
                            "content": prompt,
                        },
                        {
                            "role": "user",
                            "content": message,
                        },
                    ]
                else:
                    chat_history.append(
                        {
                            "role": "user",
                            "content": message,
                        }
                    )

                if image_base64:
                    chat_history[-1]["images"] = image_base64

                response = await self.ollama.chat(model=model, messages=chat_history, stream=False)

                # Extract response message from assistant
                if hasattr(response, "message") and hasattr(response.message, "content"):
                    assistant_reply = response.message.content

                    # remove the stuit ff inside the <think> tag for reasoning models
                    assistant_reply = assistant_reply.split("</think>")[-1]

                    # Add response to chat history
                    chat_history.append(
                        {
                            "role": "system",
                            "content": assistant_reply,
                        }
                    )
                    
                    # divide the response into 2 000 character blocks
                    assistant_reply = [assistant_reply[i:i + 2000] for i in range(0, len(assistant_reply), 2000)]

                    # Clear the oldest entry if chat history is longer than 10 entries
                    if len(chat_history) > self.max_history:
                        chat_history.pop(1)
                        chat_history.pop(1)
                else:
                    await ctx.respond("Sorry, I couldn't generate a response.")

                    # Remove the last user message if the assistant failed to respond
                    chat_history.pop(-1)

                # Save chat history to redis
                await self.redis.hset(redis_key_history, "chat_history", json.dumps(chat_history))

                for reply in assistant_reply:
                    await ctx.respond(reply)

        except Exception as e:
            await ctx.respond(f"Error occurred: {e}")


    async def __load_models_async__(self):
        """Asynchronously fetch model list after cog initialization"""
        try:
            response = await self.ollama.list()  # Await the async call properly
            
            # Ensure response has the models attribute
            if not hasattr(response, "models"):
                raise ValueError("Unexpected response format from self.ollama.list()")

            self.models = [
                {
                    "model": model.model,
                    "modified_at": model.modified_at,  # This is already a datetime object
                    "digest": model.digest,
                    "size_mb": round(model.size / 1024 / 1024, 2),  # Convert bytes to MB
                    "details": {
                        "format": model.details.format if model.details else None,
                        "family": model.details.family if model.details else None,
                        "parameter_size": model.details.parameter_size if model.details else None,
                        "quantization_level": model.details.quantization_level if model.details else None,
                    }
                }
                for model in response.models  # Iterate through models list
            ]
            self.last_updated = datetime.now()

        except Exception as e:
            print(f"Failed to load models: {e}")
    

    def __format_model_list__(self, models: List[Dict]):
        embed = discord.Embed(
            title="Model List",
            description="List of available models",
            color=discord.Color.blurple(),
            timestamp=self.last_updated
        )

        for model in models:
            embed.add_field(
                name=model["model"],
                value=f"Size: {model['size_mb']} MB\n"
                      f"Family: {model['details']['family']}\n"
                      f"Params: {model['details']['parameter_size']}\n"
                      f"Quantization: {model['details']['quantization_level']}",
                inline=False
            )
        
        return embed


    def cog_unload(self):
        pass


def setup(bot):
    bot.add_cog(ChatCommands(bot))