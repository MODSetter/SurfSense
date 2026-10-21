class GoingBackError(Exception):
    """Going back stopped after it began changing the database.

    `data_unchanged` is what the dialog may claim: true only once the copy set
    aside first is back in place.
    """

    def __init__(self, reason: str, *, data_unchanged: bool) -> None:
        super().__init__(reason)
        self.data_unchanged = data_unchanged
