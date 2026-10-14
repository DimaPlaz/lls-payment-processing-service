import dotenv
import pydantic
import pydantic_settings

dotenv.load_dotenv()


class ApiSettings(pydantic_settings.BaseSettings):
    # idempotency
    idempotency_require: bool = pydantic.Field(default=False)
    idempotency_methods: list[str] = pydantic.Field(default=["POST", "DELETE", "PUT"])
    # auth: ключ обязателен и задаётся только через окружение
    auth_key_name: str = pydantic.Field(default="X-API-Key")
    auth_key: str = pydantic.Field(min_length=1)

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="API_")


api = ApiSettings()  # pyright: ignore [reportCallIssue] -- auth_key читается из окружения
