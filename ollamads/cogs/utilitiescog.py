#  Copyright (c) 2019-2022 ThatRedKite and contributors
#  Copyright (c) 2022 diminDDL
#  License: MIT License

import discord
import aiohttp
import psutil
import si_prefix
from discord.ext import commands, bridge
from datetime import datetime
from ollamads.backend.util import EmbedColors as ec
from enum import IntEnum


class UtilityCommandsEnum(IntEnum):
    """Commands available for utility"""
    status = 0
    invite = 1
    about = 2


class UtilityCommands(commands.Cog, name="utility commands"):
    """
    Utility commands for the bot. These commands are basically informational commands.
    """
    def __init__(self, bot: commands.Bot):
        self.dirname = bot.dirname
        self.redis = bot.redis
        self.bot = bot

    
    @commands.slash_command(name="utility")
    async def utility(self, ctx: discord.ApplicationContext, command: UtilityCommandsEnum):
        """This command is used to manage the bot. These commands are only available to the bot owner."""
        match(command):
            case UtilityCommandsEnum.status:
                await self.__status__(ctx)
            case UtilityCommandsEnum.invite:
                await self.__invite__(ctx)
            case UtilityCommandsEnum.about:
                await self.__about__(ctx)
            case _:
                await ctx.respond("nyot a vawid command :rolling_eyes:")


    async def __status__(self, ctx):
        """
        Displays the status of the bot.
        """
        process = psutil.Process(self.bot.pid)
        mem = process.memory_info()[0]
        redismem = (self.redis.info())["used_memory"]

        cpu = psutil.cpu_percent(interval=None)
        ping = round(self.bot.latency * 1000, 1)
        uptime = str(datetime.now() - self.bot.starttime).split(".")[0]
        total_users = sum([users.member_count for users in self.bot.guilds])
        guilds = len(self.bot.guilds)

        embed = discord.Embed()
        embed.add_field(name="System status",
                        value=f"""RAM usage: **{si_prefix.si_format(mem + redismem)}B**
                                Redis usage: **{si_prefix.si_format(redismem)}B**
                                CPU usage: **{cpu} %**
                                uptime: **{uptime}**
                                ping: **{ping} ms**""")

        embed.add_field(name="Bot stats",
                        value=f"""guilds: **{guilds}**
                                extensions loaded: **{len(self.bot.extensions)}**
                                total users: **{total_users}**
                                bot version: **{self.bot.version}**
                                """, inline=False)
        try:
            embed.set_thumbnail(url=str(self.bot.user.avatar.url))
        except:
            pass

        if not self.bot.debugmode:
            if cpu >= 90.0:
                embed.color = 0xbb1e10
                embed.set_footer(text="Warning: CPU usage over 90%")
            else:
                embed.color = 0x00b51a
        else:
            embed.color = 0x47243c
        await ctx.respond(embed=embed)


    async def __invite__(self, ctx):
        # TODO: correct the link
        """This sends you an invite for the bot if you want to add it to one of your servers."""
        await ctx.author.send(
            f"https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=274878318592&scope=bot%20applications.commands"
        )


    async def __about__(self, ctx):
        """
        This command is here to show you what the bot is made of.
        """
        embed = discord.Embed(
            color=ec.raspberry_red,
            title="About ollamads",
            description="""A bot that allows you to connect an ollama instance to discord for LLM fun within discord.
                  This bot is licensed under the MIT license is open source and free to use for everyone.
                  The source code is available [here](https://github.com/diminDDL/discord-ollama), feel free to contribute!
                """
        )
        try:
            embed.set_thumbnail(url=str(self.bot.user.avatar.url))
        except:
            pass

        # dictionary for discord username lookup from github username
        # format: "githubusername":"discordID"
        authordict = {
            "diminDDL":"<@312591385624576001>", 
            "Cuprum77":"<@323502550340861963>"
        }

        jsonData = await self.__contributor_json__(self.bot.aiohttp_session)
        authorlist = [x["login"] for x in jsonData]
        authorlist = [x for x in authorlist if not x.lower().__contains__("bot")]
        authorlist = authorlist[:5]

        embedStr = ""
        for i in authorlist:
            if i in authordict:
                embedStr += f"{authordict[i]}\n"
            else:
                embedStr += f"{i}\n"
        embedStr += "and other [contributors](https://github.com/diminDDL/discord-ollama/graphs/contributors)"    
        embed.add_field(
            name="Authors",
            value=embedStr
        )
        embed.add_field(
            name="libraries used",
            inline=False,
            value="""
            [pycord](https://github.com/Pycord-Development/pycord)
            [aiohttp](https://github.com/aio-libs/aiohttp)
            [psutil](https://github.com/giampaolo/psutil)
            [si_prefix](https://github.com/cfobel/si-prefix)
            [redis-py](https://github.com/redis/redis-py)
            [ollama](https://github.com/ollama/ollama-python)
            """
        )

        embed.set_footer(text="Ollamads v{}".format(self.bot.version))

        await ctx.respond(embed=embed)


    async def __contributor_json__(session: aiohttp.ClientSession):
        headers = {"User-Agent": "ollamads/1.0", "content-type": "text/html"}
        async with session.get(
                f"https://api.github.com/repos/diminDDL/discord-ollama/contributors?q=contributions&order=desc",
                headers=headers) as r:
            if r.status == 200:
                jsonstr = await r.json()
            else:
                return None
        return jsonstr


def setup(bot):
    bot.add_cog(UtilityCommands(bot))
