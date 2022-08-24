async def print(ctx, output: str, entries: list):
    for entry in entries:
        if len(output + entry) > 1800:
            await ctx.respond(output)
            output = entry
        else:
            output += "\n" + entry
    await ctx.respond(output)
