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
from enum import IntEnum
from typing import List, Dict
from datetime import datetime
from discord.ext import commands
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ProcessPoolExecutor
from ollama import AsyncClient
from ollamads.backend.util import pretty_date
from ollamads.backend.util import can_change_settings


class ChatAdminCommandsEnum(IntEnum):
    """Commands available for chat admin"""
    reload = 0
    list = 1
    set = 2
    get = 3
    prompt = 4


class ChatUserCommandsEnum(IntEnum):
    """Commands available for chat user"""
    chat = 0
    clear = 1


class ChatCommands(commands.Cog):
    """
    This cog is used to allow users to chat with the model.
    """
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.default_prompt = self.bot.default_prompt
        self.redis = self.bot.redis
        self.ollama = self.bot.ollama
        self.pp = ProcessPoolExecutor(max_workers=1)    
        self.sep = asyncio.Semaphore(2)
        self.ll = asyncio.get_event_loop()
        
        bot.loop.create_task(self.__load_models_async__())


    @commands.guild_only()
    @commands.slash_command(name="config")
    async def chat_admin_cmd(self, ctx: discord.ApplicationContext, command: ChatAdminCommandsEnum, model: str = ""):
        """
        This command is used to manage the chat settings for the bot.
        """
        if command == ChatAdminCommandsEnum.reload:
            await self.__reload__(ctx)
        elif command == ChatAdminCommandsEnum.list:
            await self.__list__(ctx)
        elif command == ChatAdminCommandsEnum.set:
            await self.__set__(ctx, model)
        elif command == ChatAdminCommandsEnum.get:
            await self.__get__(ctx)
        elif command == ChatAdminCommandsEnum.prompt:
            await self.__prompt__(ctx, model)
        else:
            await ctx.respond("Invalid command.")


    @commands.guild_only()
    @commands.slash_command(name="chat")
    async def chat_user_cmd(self, ctx: discord.ApplicationContext, command: ChatUserCommandsEnum, message: str = ""):
        """
        This command is used to chat with the bot.
        """
        if command == ChatUserCommandsEnum.chat:
            await self.__chat__(ctx, message)
        elif command == ChatUserCommandsEnum.clear:
            await self.__clear__(ctx)
        else:
            await ctx.respond("Invalid command.")


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
        await ctx.respond(embed=self.__format_model_list__(self.models))
    

    async def __set__(self, ctx: discord.ApplicationContext, model = ''):
        """
        This command is used to select a model for a specific channel.
        """
        if not model:
            return await ctx.respond("Please provide a model name.")

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


    async def __chat__(self, ctx: discord.ApplicationContext, message: str):
        """
        This command is used to chat with the selected model.
        """
        chat_history = await self.__llm_format_history__(ctx, message)
        await self.__llm_chat__(ctx, chat_history)
        await ctx.respond("Message sent.", ephemeral=True)
        

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


    async def __clear__(self, ctx: discord.ApplicationContext):
        """
        Clear your chat history for this channel.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:user:{ctx.author.id}:history"
        await self.redis.hdel(redis_key, "chat_history")
        await ctx.respond("Chat history cleared.", ephemeral=True)
        

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Listen for messages and respond to mentions.
        """
        if not message.guild:
            return

        if message.author.bot:
            return
        
        if message.content == "":
            return
        
        ctx = await self.bot.get_context(message)
        message_content = message.content

        image_url = []
        if message.attachments:
            for attachment in message.attachments:
                image_url.append(attachment.url)

        if message.reference and message.reference.message_id: 
            referenced_message = await message.channel.fetch_message(message.reference.message_id)

            if referenced_message.author != self.bot.user:
                if referenced_message.attachments:
                    for attachment in referenced_message.attachments:
                        image_url.append(attachment.url)

            if referenced_message.author == self.bot.user:
                await self.__llm_chat__(ctx, message_content, image_url[0])
            elif self.bot.user in message.mentions:
                await self.__llm_chat__(ctx, message_content, image_url[0])

        elif self.bot.user in message.mentions:
            await self.__llm_chat__(ctx, message_content, image_url[0])


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
                    # limit response to 2000 characters
                    if len(assistant_reply) > 2000:
                        assistant_reply = assistant_reply[:2000]

                    # Add response to chat history
                    chat_history.append(
                        {
                            "role": "system",
                            "content": assistant_reply,
                        }
                    )

                    # Clear the oldest entry if chat history is longer than 10 entries
                    if len(chat_history) > 10:
                        chat_history.pop(1)
                        chat_history.pop(2)
                else:
                    assistant_reply = "Sorry, I couldn't generate a response."

                    # Remove the last user message if the assistant failed to respond
                    chat_history.pop(-1)

                # Save chat history to redis
                await self.redis.hset(redis_key_history, "chat_history", json.dumps(chat_history))

                await ctx.respond(assistant_reply)

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