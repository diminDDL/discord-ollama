#  Copyright (c) 2025 diminDDL, Cuprum77
#  License: MIT License

import discord
from discord.ext import commands, tasks
from discord.ext.commands.errors import CommandInvokeError


class ListenerCog(commands.Cog):
    """
    ListenerCog is a cog that contains listeners for the bot.
    """
    def __init__(self, bot):
        self.dirname = bot.dirname
        self.bot: discord.Client = bot


    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: CommandInvokeError):
        match type(error):
            case commands.CommandOnCooldown:
                await ctx.respond(f"Sorry, but this command is on cooldown! Please wait {int(error.retry_after)} seconds.", ephemeral=True)

            case commands.CommandInvokeError:
                if self.bot.debugmode:
                    await ctx.respond(repr(error), ephemeral=True)
                raise error
            
            case commands.CheckFailure:
                await ctx.respond("A check has failed! This command might be disabled on the server or you lack permission", ephemeral=True)

            case commands.MissingPermissions:
                await ctx.respond("Sorry, but you don't have the permissions to do this", ephemeral=True)

            case commands.NotOwner:
                await ctx.respond("haha you weawwy think im ***that*** submissive?!", ephemeral=True)

            case commands.ChannelNotFound:
                await ctx.respond("The channel you specified was not found!", ephemeral=True)

            case commands.RoleNotFound:
                await ctx.respond("The role you specified was not found!", ephemeral=True)


    @commands.Cog.listener()
    async def on_ready(self):
        print("\nBot successfully started!")
        await self.bot.change_presence(
            activity=discord.Activity(name="Pondering...", type=1),
            status=discord.Status.online,
        )


    @commands.Cog.listener()
    async def on_slash_command_error(self, ctx, ex):
        raise ex


def setup(bot):
    bot.add_cog(ListenerCog(bot))
