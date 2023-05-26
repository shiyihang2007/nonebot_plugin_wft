from .game import game


class pool:
    gameList: list[game]

    def findGame(self, group: str) -> game:
        for i in self.gameList:
            if i.group == group:
                return i
        raise KeyError
