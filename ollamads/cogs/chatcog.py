#  Copyright (c) 2022 diminDDL
#  License: MIT License

from re import T
import discord
import requests
import asyncio
import functools
import re
from typing import List, Dict
from datetime import datetime
from ollama import AsyncClient
from concurrent.futures import ProcessPoolExecutor
from time import sleep
from io import BytesIO
from urllib.parse import urlparse, parse_qs
from time import mktime
from discord.ext import commands, tasks, bridge
from ollamads.backend.util import pretty_date
from ollamads.backend.util import can_change_settings


class Chat(commands.Cog, name="piLocate"):
    """
    This cog is used to get the latest news from rpilocator.com
    """
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.redis = self.bot.redis
        self.ollama = self.bot.ollama
        self.pp = ProcessPoolExecutor(max_workers=1)    
        self.sep = asyncio.Semaphore(2)
        self.ll = asyncio.get_event_loop()
        
        bot.loop.create_task(self.load_models_async())

    async def load_models_async(self):
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

    

    def format_model_list(self, models: List[Dict]):
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


    @bridge.bridge_command(aliases=["reloadmodels"])
    async def reload_models(self, ctx: bridge.BridgeContext):
        """
        This command is used to reload the model list.
        """
        await self.load_models_async()
        await ctx.respond("Model list reloaded.")


    @bridge.bridge_command(aliases=["listmodels"])
    async def list_models(self, ctx: bridge.BridgeContext):
        """
        This command is used to list the available models.
        """
        await ctx.respond(embed=self.format_model_list(self.models))
    
    @bridge.bridge_command(aliases=["selectmodel"])
    async def select_model(self, ctx: bridge.BridgeContext, model = ''):
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

    @bridge.bridge_command(aliases=["getmodel"])
    async def get_model(self, ctx: bridge.BridgeContext):
        """
        This command is used to get the selected model for a specific channel.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        model = await self.redis.hget(redis_key, "model")

        if not model:
            return await ctx.respond("No model selected for this channel.")

        await ctx.respond(f"Model selected for this channel: **{model}**")


    @bridge.bridge_command(aliases=["llmchat"])
    async def llm_chat(self, ctx: bridge.BridgeContext, *, message: str):
        """
        This command is used to chat with the selected model.
        """
        redis_key = f"guild:{ctx.guild.id}:channel:{ctx.channel.id}:settings"
        model = await self.redis.hget(redis_key, "model")

        if not model:
            return await ctx.respond("No model selected for this channel.")

        try:
            async with ctx.typing():
                # Properly formatted chat history for Ollama
                chat_history = [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant.",
                    },
                    {
                        "role": "user",
                        "content": message,
                    }
                ]

                response = await self.ollama.chat(model=model, messages=chat_history, stream=False)

                # Extract response message from assistant
                if hasattr(response, "message") and hasattr(response.message, "content"):
                    assistant_reply = response.message.content
                else:
                    assistant_reply = "Sorry, I couldn't generate a response."

                await ctx.respond(assistant_reply)

        except Exception as e:
            await ctx.respond(f"Error occurred: {e}")


    def cog_unload(self):
        pass


def setup(bot):
    bot.add_cog(Chat(bot))
