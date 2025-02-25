#  Copyright (c) 2019-2022 ThatRedKite and contributors
#  Copyright (c) 2022 diminDDL
#  License: MIT License

import asyncio
import glob
import os
import discord
from datetime import datetime, timezone
from discord.ext import commands


class EmbedColors:
    blood_orange = 0xe25303
    lime_green = 0x00b51a
    traffic_red = 0xbb1e10
    purple_violet = 0x47243c
    light_grey = 0xc5c7c4
    sulfur_yellow = 0xf1dd38
    ultramarine_blue = 0x00387b
    telemagenta = 0xbc4077
    raspberry_red = 0x9b0f0f
    cum = 0xfbf5e9


async def can_change_settings(ctx: commands.Context):
    """
    Checks if the user has the permission to change settings.
    """
    channel: discord.TextChannel = ctx.channel
    isowner = await ctx.bot.is_owner(ctx.author)
    isadmin = channel.permissions_for(ctx.author).administrator
    ischanneleditor = channel.permissions_for(ctx.author).manage_channels
    return isowner or isadmin or ischanneleditor


def pretty_date(time=False):
    """
    Get a datetime object or an int() Epoch timestamp and return a
    pretty string like 'an hour ago', 'Yesterday', '3 months ago',
    'just now', etc.
    """
    now = datetime.now(timezone.utc)  # Ensure `now` is timezone-aware
    
    if isinstance(time, int):  # Convert timestamp to datetime
        time = datetime.fromtimestamp(time, timezone.utc)
    elif isinstance(time, datetime):
        if time.tzinfo is None:  # If `time` is naive, make it timezone-aware
            time = time.replace(tzinfo=timezone.utc)

    if not time:
        return "just now"

    diff = now - time
    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        if second_diff < 60:
            return f"{second_diff} seconds ago"
        if second_diff < 120:
            return "a minute ago"
        if second_diff < 3600:
            return f"{second_diff // 60} minutes ago"
        if second_diff < 7200:
            return "an hour ago"
        if second_diff < 86400:
            return f"{second_diff // 3600} hours ago"
    if day_diff == 1:
        return "Yesterday"
    if day_diff < 7:
        return f"{day_diff} days ago"
    if day_diff < 31:
        return f"{day_diff // 7} weeks ago"
    if day_diff < 365:
        return f"{day_diff // 30} months ago"
    return f"{day_diff // 365} years ago"


async def errormsg(ctx=None, msg: str = "", exc="", embed_only=False):
    if not embed_only:
        embed = discord.Embed(title="**ERROR!**", description=msg)
        embed.color = EmbedColors.traffic_red
        embed.set_footer(text=exc)
        await ctx.send(embed=embed, delete_after=5.0)
        await asyncio.sleep(5.0)
    else:
        embed = discord.Embed(title="**ERROR!**", description=msg)
        embed.color = EmbedColors.traffic_red
        embed.set_footer(text=exc)
        return embed


def clear_temp_folder():
    """
        a simple function to clear the temp data folder of the bot+
    """
    cleanupfiles = glob.glob(os.path.join("/tmp/", "*.png"))
    cleanupfiles += glob.glob(os.path.join("/tmp/", "*.webp"))
    cleanupfiles += glob.glob(os.path.join("/tmp/", "*.gif"))
    cleanupfiles += glob.glob(os.path.join("/tmp/", "*.mp3"))
    for file in cleanupfiles:
        os.remove(file)



