import importlib
from pathlib import Path
from typing import Any

from wechat.image_keys import ImageKeys


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

    def download(self, mode: str | None = None) -> Path:
        path = self._source.image(self.user, self.row, mode)
        self.image_kind = self._source.image_kind
        return path


class DatabaseSource:
    """
    Read only selected conversations and local media without invoking UI APIs.
    """

    def __init__(self, directory: Path, images: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        module = importlib.import_module("wechatauto.db")
        from wechat.cached_media import CachedMedia

        self.db = module.WeChatDB(workdir=str(directory))
        self.media = CachedMedia(self.db, save_dir=str(images))
        self._keys = ImageKeys(directory / "image-key.bin")
        self.thumbnail_only = False
        self.image_mode = "compressed"

    def resolve(self, name: str) -> str:
        _, separator, identifier = name.rpartition(" [")
        if separator and identifier.endswith("]"):
            identifier = identifier[:-1]
            matches = [
                row
                for row in self.db.search_contact(identifier)
                if row["username"] == identifier
            ]
            if len(matches) == 1:
                return identifier
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

    def image(
        self, user: str, row: dict[str, Any], exact_mode: str | None = None
    ) -> Path:
        mode = exact_mode or (
            "thumbnail"
            if getattr(self, "thumbnail_only", False)
            else getattr(self, "image_mode", "compressed")
        )
        if mode not in {"thumbnail", "compressed"}:
            raise ValueError("Unknown image source mode")
        tier = "thumb" if mode == "thumbnail" else "mid"
        raw = self.db.get_message_row(
            user, row["local_id"], local_type=3, shard=row.get("shard")
        )
        if not raw:
            raise ValueError("The image message is no longer available")
        image_id = self.media._img_md5(raw)
        if image_id is None:
            raise FileNotFoundError("The image cache identifier is unavailable")
        files = self.media._image_files(user, image_id)
        target = files.get(tier)
        if not target:
            raise FileNotFoundError("WeChat has not cached this image yet")
        arguments = {"shard": row.get("shard"), "tier": tier}
        probe = self.media._probe_ct(target[0])
        if probe:
            key, xor = self._keys.resolve(self.media, probe)
            arguments.update(aes_key=key, xor_key=xor)
        result = self.media.download_image(user, row["local_id"], **arguments)
        if not result or not Path(result).is_file():
            raise FileNotFoundError("No complete cached image is available")
        self.image_kind = mode
        return Path(result)
