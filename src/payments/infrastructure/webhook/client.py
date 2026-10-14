import httpx

from payments.infrastructure import settings
from payments.service import interfaces


class HTTPXWebhookClient(interfaces.IWebhookClient):
    async def notify(self, url: str, idempotency_key: str, data: dict | None = None) -> None:
        async with httpx.AsyncClient(timeout=settings.webhook.timeout) as client:
            r = await client.post(
                url=url,
                json=data or {},
                headers={"Idempotency-Key": idempotency_key},
            )
            r.raise_for_status()
