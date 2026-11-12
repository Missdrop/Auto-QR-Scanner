class WeChat:
    """
    Own interaction with the logged-in Windows WeChat client.

    Group monitoring and image retrieval are not implemented yet.
    """

    def __init__(self) -> None:
        # Keep client integration inside this object.
        self._chat_names: list[str] = []
