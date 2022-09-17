class Config:
    def __init__(self):
        with open('data/bot.token', 'r') as file:
            self.token = file.read().strip()
