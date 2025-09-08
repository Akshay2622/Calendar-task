from dotenv import load_dotenv
import os

load_dotenv()

class Settings:
    import os

    DATABASE_URL = (
    f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)

    APP_NAME: str = "Simple Calendar"

settings = Settings()

