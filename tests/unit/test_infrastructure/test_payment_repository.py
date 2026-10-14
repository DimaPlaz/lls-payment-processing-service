import datetime
import decimal
from unittest import mock

import faker as faker_lib
import pydantic
import pytest
from sqlalchemy import exc as sa_exc

from payments.domain import entities, enums
from payments.infrastructure.database import orm
from payments.infrastructure.repositories import payment_repository as repository_module
from payments.service import exceptions


class DBAPIError(Exception):
    """Аналог ошибки драйвера, которую SQLAlchemy кладёт в IntegrityError.orig"""

    def __init__(self, sqlstate: str):
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


@pytest.fixture
def create_kwargs(faker: faker_lib.Faker) -> dict:
    return {
        "amount": decimal.Decimal("100.50"),
        "currency": enums.Currency.RUB,
        "description": faker.sentence(),
        "meta": {"order_id": faker.uuid4()},
        "idempotency_key": faker.uuid4(),
        "webhook_url": pydantic.HttpUrl(faker.url()),
    }


@pytest.fixture
def session() -> mock.AsyncMock:
    return mock.AsyncMock()


@pytest.fixture
def repository(session: mock.AsyncMock) -> repository_module.SqlAlchemyPaymentRepository:
    return repository_module.SqlAlchemyPaymentRepository(session)


class TestCreatePayment:
    async def test_create_payment_positive(
        self,
        session: mock.AsyncMock,
        repository: repository_module.SqlAlchemyPaymentRepository,
        create_kwargs: dict,
    ):
        # Arrange
        session.scalar.return_value = orm.Payment(
            id=1,
            status=enums.PaymentStatus.PENDING,
            created_at=datetime.datetime.now(datetime.UTC),
            processed_at=None,
            **create_kwargs | {"webhook_url": str(create_kwargs["webhook_url"])},
        )

        # Act
        payment = await repository.create(**create_kwargs)

        # Assert
        assert payment.id == 1
        assert payment.idempotency_key == create_kwargs["idempotency_key"]

    async def test_create_payment_duplicate_idempotency_key_negative(
        self,
        session: mock.AsyncMock,
        repository: repository_module.SqlAlchemyPaymentRepository,
        create_kwargs: dict,
    ):
        # Arrange
        session.scalar.side_effect = sa_exc.IntegrityError(
            statement="INSERT INTO payments ...",
            params={},
            orig=DBAPIError(sqlstate=repository_module.UNIQUE_VIOLATION),
        )

        # Act
        # Assert
        with pytest.raises(exceptions.PaymentAlreadyExists):
            await repository.create(**create_kwargs)

    async def test_create_payment_other_integrity_error_negative(
        self,
        session: mock.AsyncMock,
        repository: repository_module.SqlAlchemyPaymentRepository,
        create_kwargs: dict,
    ):
        # Arrange
        not_null_violation = "23502"
        session.scalar.side_effect = sa_exc.IntegrityError(
            statement="INSERT INTO payments ...",
            params={},
            orig=DBAPIError(sqlstate=not_null_violation),
        )

        # Act
        # Assert
        with pytest.raises(sa_exc.IntegrityError):
            await repository.create(**create_kwargs)


class TestUpdatePayment:
    @pytest.mark.parametrize(("rowcount", "expected"), [(1, True), (0, False)], ids=["pending", "already_final"])
    async def test_update_payment_positive(
        self,
        session: mock.AsyncMock,
        repository: repository_module.SqlAlchemyPaymentRepository,
        create_kwargs: dict,
        rowcount: int,
        expected: bool,
    ):
        # Arrange
        session.execute.return_value = mock.Mock(rowcount=rowcount)
        payment = entities.Payment(
            id=1,
            status=enums.PaymentStatus.SUCCEEDED,
            created_at=datetime.datetime.now(datetime.UTC),
            processed_at=datetime.datetime.now(datetime.UTC),
            **create_kwargs,
        )

        # Act
        finalized = await repository.update(payment)

        # Assert
        assert finalized is expected
