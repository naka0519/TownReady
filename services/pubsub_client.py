from __future__ import annotations

import json
from typing import Any, Dict, Optional

from google.cloud import pubsub_v1

from .config import Settings


class Publisher:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        self.client = pubsub_v1.PublisherClient()
        self.topic_path = self.client.topic_path(self.settings.project, self.settings.pubsub_topic)

    def publish_json(self, data: Dict[str, Any], attributes: Optional[Dict[str, str]] = None) -> str:
        payload = json.dumps(data).encode("utf-8")
        future = self.client.publish(self.topic_path, payload, **(attributes or {}))
        return future.result(timeout=30)

