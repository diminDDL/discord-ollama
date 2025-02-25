#  Copyright (c) 2025 diminDDL, Cuprum77
#  License: MIT License

from discord.commands import SlashCommandGroup
from discord.ext import commands
import discord
import os
from enum import IntEnum


class SudoCommandsEnum(IntEnum):
    """Commands available for sudo"""
    echo = 0
    debug = 1
    reload = 2
    restart = 3
    shutdown = 4
    update = 5


class SudoCommands(commands.Cog):
    """This cog contains commands that are used to manage the bot. These commands are only available to the bot owner."""
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.dirname = bot.dirname
        self.redis = self.bot.redis


    @commands.is_owner()
    @commands.slash_command(name="sudo")
    async def sudo(self, ctx: discord.ApplicationContext, command: SudoCommandsEnum, message: str = ""):
        """This command is used to manage the bot. These commands are only available to the bot owner."""
        match(command):
            case SudoCommandsEnum.echo:
                await self.__echo__(ctx, message=message)
            case SudoCommandsEnum.debug:
                await self.__debug_mode__(ctx)
            case SudoCommandsEnum.reload:
                await self.__reload__(ctx)
            case SudoCommandsEnum.restart:
                await self.__restart__(ctx)
            case SudoCommandsEnum.shutdown:
                await self.__shutdown__(ctx)
            case SudoCommandsEnum.update:
                await self.__update__(ctx)
            case _:
                await ctx.respond("That was not a valid command!", ephemeral=True)
            

    async def __echo__(self, ctx: discord.ApplicationContext, message: str):
        await ctx.respond(message)


    async def __debug_mode__(self, ctx: discord.ApplicationContext):
        self.bot.debugmode = not self.bot.debugmode
        await ctx.respond(f"Debug mode is now {self.bot.debugmode}", ephemeral=True)


    async def __reload__(self, ctx: discord.ApplicationContext):
        print("Reloading the extensions", ephemeral=True)
        extensions = list(self.bot.extensions.keys())
        for extension in extensions:
            try:
                self.bot.reload_extension(extension)
                print(f"Reloaded {extension}")
            except Exception as exc:
                raise exc
        await ctx.respond(f"extensions w-wewoaded")


    async def __restart__(self, ctx: discord.ApplicationContext):
        await ctx.respond("Restarting the bot", ephemeral=True)
        try:
            await self.bot.aiohttp_session.close()
            await self.bot.close()
        except Exception as exp:
            print(exp)
            await self.bot.aiohttp_session.close()
            await self.bot.close()
            exit(0)
        finally:
            os.system(f"python3 -m ollamads")


    async def __shutdown__(self, ctx: discord.ApplicationContext):
        await ctx.respond("see you in bed mastew ^w^", ephemeral=True)
        await self.bot.aiohttp_session.close()
        await self.bot.close()
        exit(0)

    
    async def __update__(self, ctx: discord.ApplicationContext):
        os.system("git pull")
        commit_message = os.popen("git log -1 --pretty=%B").read().strip()
        commit_hash = os.popen("git rev-parse --short HEAD").read().strip()
        await ctx.respond(f"Current version is ```{commit_hash}: {commit_message}```", ephemeral=True)
        # restart the bot
        await self.__restart__(ctx)


def setup(bot):
    bot.add_cog(SudoCommands(bot))
