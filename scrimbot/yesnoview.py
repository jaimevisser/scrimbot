import discord.ui


class YesNoView(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.value = None
        self.__interaction = None

    @discord.ui.button(label="No", style=discord.ButtonStyle.red)
    async def no(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        self.__interaction = interaction
        self.stop()

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green)
    async def yes(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        self.__interaction = interaction
        self.stop()

    async def respond(self, text):
        await self.__interaction.response.edit_message(content=text, view=None)
