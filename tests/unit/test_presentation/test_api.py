import typing

import faker as faker_lib
import httpx
import pytest
from fastapi import status

from payments.domain import entities
from payments.presentation.api.settings import api as api_settings


@pytest.fixture
def payment_body(faker: faker_lib.Faker) -> dict[str, typing.Any]:
    return {
        "amount": "100.50",
        "currency": "RUB",
        "description": faker.sentence(),
        "meta": {"order_id": faker.uuid4()},
        "webhook_url": faker.url(),
    }


@pytest.fixture
def idempotency_headers(faker: faker_lib.Faker) -> dict[str, str]:
    return {"Idempotency-Key": faker.uuid4()}


def validation_errors(response: httpx.Response) -> list[tuple[list[str | int], str]]:
    """Пары (loc, type) из ответа 422"""
    return [(error["loc"], error["type"]) for error in response.json()["detail"]]


class TestCreatePayment:
    """POST /payments/"""

    async def test_create_payment_positive(
        self,
        api_client: httpx.AsyncClient,
        payment_body: dict[str, typing.Any],
        idempotency_headers: dict[str, str],
    ):
        # Arrange
        # Act
        response = await api_client.post("/payments", json=payment_body, headers=idempotency_headers)

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED

    async def test_create_payment_without_meta_positive(
        self,
        api_client: httpx.AsyncClient,
        payment_body: dict[str, typing.Any],
        idempotency_headers: dict[str, str],
    ):
        # Arrange
        del payment_body["meta"]

        # Act
        response = await api_client.post("/payments", json=payment_body, headers=idempotency_headers)

        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED

    @pytest.mark.parametrize(
        ("field", "value", "error_type"),
        [
            ("amount", "0", "greater_than"),
            ("amount", "-1", "greater_than"),
            ("amount", "10.123", "decimal_max_places"),
            ("amount", "10000000000.00", "decimal_whole_digits"),
            ("currency", "GBP", "enum"),
            ("description", "x" * 256, "string_too_long"),
            ("webhook_url", "not-a-url", "url_parsing"),
        ],
    )
    async def test_create_payment_invalid_body_negative(
        self,
        api_client: httpx.AsyncClient,
        payment_body: dict[str, typing.Any],
        idempotency_headers: dict[str, str],
        field: str,
        value: str,
        error_type: str,
    ):
        # Arrange
        payment_body[field] = value

        # Act
        response = await api_client.post("/payments", json=payment_body, headers=idempotency_headers)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert validation_errors(response) == [(["body", field], error_type)]

    @pytest.mark.parametrize("field", ["amount", "currency", "description", "webhook_url"])
    async def test_create_payment_missing_required_field_negative(
        self,
        api_client: httpx.AsyncClient,
        payment_body: dict[str, typing.Any],
        idempotency_headers: dict[str, str],
        field: str,
    ):
        # Arrange
        del payment_body[field]

        # Act
        response = await api_client.post("/payments", json=payment_body, headers=idempotency_headers)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert validation_errors(response) == [(["body", field], "missing")]

    async def test_create_payment_without_idempotency_key_negative(
        self,
        api_client: httpx.AsyncClient,
        payment_body: dict[str, typing.Any],
    ):
        # Arrange
        # Act
        response = await api_client.post("/payments", json=payment_body)

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert validation_errors(response) == [(["header", "Idempotency-Key"], "missing")]


    async def test_create_payment_duplicate_idempotency_key_negative(
        self,
        api_client: httpx.AsyncClient,
        payment_factory: typing.Callable[..., entities.Payment],
        payment_body: dict[str, typing.Any],
        idempotency_headers: dict[str, str],
    ):
        # Arrange
        idempotency_key = idempotency_headers["Idempotency-Key"]
        payment_factory(idempotency_key=idempotency_key)

        # Act
        response = await api_client.post("/payments", json=payment_body, headers=idempotency_headers)

        # Assert
        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {"detail": f"Payment with idempotency key {idempotency_key} already exists"}


class TestGetPayment:
    """GET /payments/{payment_id}"""

    async def test_get_payment_positive(
        self,
        api_client: httpx.AsyncClient,
        payment_factory: typing.Callable[..., entities.Payment],
    ):
        # Arrange
        payment = payment_factory()

        # Act
        response = await api_client.get(f"/payments/{payment.id}")

        # Assert
        assert response.status_code == status.HTTP_200_OK

    async def test_get_payment_not_found_negative(
        self,
        api_client: httpx.AsyncClient,
        payment_factory: typing.Callable[..., entities.Payment],
    ):
        # Arrange
        payment = payment_factory()
        missing_payment_id = payment.id + 1

        # Act
        response = await api_client.get(f"/payments/{missing_payment_id}")

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": f"Payment {missing_payment_id} not found"}

    async def test_get_payment_invalid_id_negative(self, api_client: httpx.AsyncClient):
        # Arrange
        # Act
        response = await api_client.get("/payments/abc")

        # Assert
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
        assert validation_errors(response) == [(["path", "payment_id"], "int_parsing")]


class TestAuth:
    """auth"""

    async def test_request_without_api_key_negative(
        self,
        api_client: httpx.AsyncClient,
        payment_factory: typing.Callable[..., entities.Payment],
    ):
        # Arrange
        payment = payment_factory()
        api_client.headers.pop(api_settings.auth_key_name)

        # Act
        response = await api_client.get(f"/payments/{payment.id}")

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "Not authenticated"}

    async def test_request_with_wrong_api_key_negative(
        self,
        api_client: httpx.AsyncClient,
        payment_factory: typing.Callable[..., entities.Payment],
    ):
        # Arrange
        payment = payment_factory()

        # Act
        response = await api_client.get(f"/payments/{payment.id}", headers={api_settings.auth_key_name: "wrong-key"})

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {"detail": "Invalid or missing API key"}
