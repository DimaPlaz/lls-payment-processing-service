import pydantic
import pydantic_settings


class Db(pydantic_settings.BaseSettings):
    """Database config"""

    hostname: str = pydantic.Field(default="nonset")
    port: pydantic.PositiveInt = pydantic.Field(default=5432)
    database: str = pydantic.Field(default="nonset")

    user: str = pydantic.Field(default="nonset")
    password: str = pydantic.Field(default="nonset")

    pool_size: pydantic.PositiveInt = pydantic.Field(default=10)

    @property
    def dsn(self) -> pydantic.PostgresDsn:
        return pydantic.PostgresDsn(  # pyright: ignore [reportCallIssue]
            f"postgresql+asyncpg://{self.user}:{self.password}@{self.hostname}:{self.port}/{self.database}",
        )

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="DB_")


class RabbitMQ(pydantic_settings.BaseSettings):
    """RabbitMQ config"""

    hostname: str = pydantic.Field(default="nonset")
    port: pydantic.PositiveInt = pydantic.Field(default=5672)

    user: str = pydantic.Field(default="nonset")
    password: str = pydantic.Field(default="nonset")

    durable: bool = pydantic.Field(default=True)
    payments_exchange: str = pydantic.Field(default="payments")
    retry_exchange: str = pydantic.Field(default="payments.retry")
    dl_exchange: str = pydantic.Field(default="payments.dlx")
    payments_queue: str = pydantic.Field(default="payments.new")
    dl_queue: str = pydantic.Field(default="payments.dlq")
    retry_delays: list[pydantic.PositiveInt] = pydantic.Field(
        default=[3, 6, 12],
        description="Задержки повторных попыток в секундах, число элементов = число повторов",
    )

    @property
    def dsn(self) -> pydantic.AmqpDsn:
        return pydantic.AmqpDsn(  # pyright: ignore [reportCallIssue]
            f"amqp://{self.user}:{self.password}@{self.hostname}:{self.port}/",
        )

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="RABBITMQ_")


class Webhook(pydantic_settings.BaseSettings):
    """Webhook client config"""

    timeout: pydantic.PositiveFloat = pydantic.Field(default=10.0, description="Таймаут запроса в секундах")

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="WEBHOOK_")


db = Db()
rabbitmq = RabbitMQ()
webhook = Webhook()
