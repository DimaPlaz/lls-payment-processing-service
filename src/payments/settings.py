import logging

import dotenv
import pydantic
import pydantic_settings

dotenv.load_dotenv()


class AppSettings(pydantic_settings.BaseSettings):
    name: str = pydantic.Field(default="llc_mkk_basis_test")
    debug: bool = pydantic.Field(default=True)
    log_level: str = pydantic.Field(default="INFO")

    model_config = pydantic_settings.SettingsConfigDict(env_prefix="APP_")


app = AppSettings()


def configure_logging() -> None:
    logging.basicConfig(level=app.log_level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
