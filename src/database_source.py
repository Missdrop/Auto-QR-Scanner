import importlib
from pathlib import Path
from typing import Any

from .image_keys import ImageKeys


class DatabasePhoto:
    """
    Represent one incoming image using database identity rather than screen position.
    """

    def __init__(
        self, source: "DatabaseSource", user: str, row: dict[str, Any]
    ) -> None:
        self._source = source
        self.user = user
        self.row = row
        self.id = f"{row.get('shard', '')}:{row['local_id']}:{row['sort_seq']}"
        self.type = "image" if row["type"] in {"图片", "image"} else "other"
        sender = row.get("sender_username")
        self.attr = "unknown"
        if sender:
            self.attr = "self" if sender == source.db.wxid else "friend"

    def download(self) -> Path:
        return self._source.image(self.user, self.row)


class DatabaseSource:
    """
    Read only selected conversations and local media without invoking UI APIs.
    """

    def __init__(self, directory: Path, images: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        module = importlib.import_module("wechatauto.db")
        media = importlib.import_module("wechatauto.media")
        self.db = module.WeChatDB(workdir=str(directory))
        self.media = media.MediaDownloader(self.db, save_dir=str(images))
        self._keys = ImageKeys(directory / "image-key.bin")
        self.thumbnail_only = False

    def resolve(self, name: str) -> str:
        contacts = self.db.search_contact(name)
        matches = {
            row["username"]
            for row in contacts
            if name in (row.get("username"), row.get("nick_name"), row.get("remark"))
        }
        if len(matches) != 1:
            raise ValueError("Use an exact, unambiguous chat name or WeChat identifier")
        return matches.pop()

    def latest(self, user: str, limit: int = 100) -> list[DatabasePhoto]:
        return [
            DatabasePhoto(self, user, row) for row in self.db.get_messages(user, limit)
        ]

    def after(self, user: str, sequence: int) -> list[DatabasePhoto]:
        rows = self.db.get_new_messages(user, since_seq=sequence, limit=200)
        return [DatabasePhoto(self, user, row) for row in rows]

    def image(self, user: str, row: dict[str, Any]) -> Path:
        thumbnail_only = getattr(self, "thumbnail_only", False)
        arguments = {
            "shard": row.get("shard"),
            "tier": "thumb" if thumbnail_only else "best",
        }
        raw = self.db.get_message_row(
            user, row["local_id"], local_type=3, shard=row.get("shard")
        )
        if not raw:
            raise ValueError("The image message is no longer available")
        files = self.media._image_files(user, self.media._img_md5(raw))
        target = (
            files.get("thumb")
            if thumbnail_only
            else (files.get("original") or files.get("mid") or files.get("thumb"))
        )
        if not target:
            raise FileNotFoundError("WeChat has not cached this image yet")
        probe = self.media._probe_ct(target[0])
        if probe:
            key, xor = self._keys.resolve(self.media, probe)
            arguments.update(aes_key=key, xor_key=xor)
        result = self.media.download_image(user, row["local_id"], **arguments)
        if not result or not Path(result).is_file():
            raise FileNotFoundError("No complete cached image is available")
        return Path(result)

    def original(self, user: str, row: dict[str, Any], name: str) -> Path | None:
        raw = self.db.get_message_row(
            user, row["local_id"], local_type=3, shard=row.get("shard")
        )
        if not raw:
            return None
        files = self.media._image_files(user, self.media._img_md5(raw))
        target = files.get("original") or files.get("mid") or files.get("thumb")
        if not target:
            return None
        arguments: dict[str, Any] = {}
        probe = self.media._probe_ct(target[0])
        if probe:
            key, xor = self._keys.resolve(self.media, probe)
            arguments.update(aes_key=key, xor_key=xor)
        result = self.media.download_image_original(
            user,
            row["local_id"],
            shard=row.get("shard"),
            chat_name=name,
            timeout=15,
            max_scrolls=2,
            **arguments,
        )
        return Path(result) if result else None
