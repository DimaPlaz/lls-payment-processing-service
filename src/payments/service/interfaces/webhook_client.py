import abc


class IWebhookClient(abc.ABC):
    @abc.abstractmethod
    async def notify(self, url: str, idempotency_key: str, data: dict | None = None) -> None:
        raise NotImplementedError
