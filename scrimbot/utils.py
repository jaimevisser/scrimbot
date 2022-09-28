import discord


async def output(ctx, lists: list[str], title: str, ephemeral):
    embed = discord.Embed(title=title,
                          type="rich",
                          colour=discord.Colour.from_rgb(0, 0, 0)
                          )

    for content in lists:
        embed.add_field(name="-",
                        value=content,
                        inline=False)

    await ctx.respond(content="", embeds=[embed], ephemeral=ephemeral)


async def print(ctx, content: str, entries: list, title: str = None, ephemeral=True):
    data = []
    for entry in entries:
        if len(content + entry) > 1024:
            data.append(content)
            content = entry
            if len(data) == 4:
                await output(ctx, data, title, True)
                data = []
        else:
            content += "\n" + entry
    data.append(content)
    await output(ctx, data, title, ephemeral)
