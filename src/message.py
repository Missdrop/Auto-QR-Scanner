from datetime import datetime
from pathlib import Path


class ImageMessage:
    """
    Describe a received image and its source chat.
    """

    def __init__(
        self, message_id: str, chat_name: str, image_path: Path, received_at: datetime
    ) -> None:
        self.message_id = message_id
        self.chat_name = chat_name
        self.image_path = image_path
        self.received_at = received_at
