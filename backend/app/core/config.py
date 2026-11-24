from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "LearnForge AI"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    SECRET_KEY: str = "learnforge_dev_secret_key_phase0_setup_1234567890"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    
    # SQLite local file database (async driver aiosqlite)
    DATABASE_URL: str = "sqlite+aiosqlite:///./learnforge.db"
    
    # Local storage paths
    CHROMA_PERSIST_DIRECTORY: str = "./chroma_data"
    UPLOAD_DIR: str = "./uploads"
    
    # Hybrid AI Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LOCAL_MODEL: str = "qwen2.5:3b"
    
    OPENAI_API_KEY: str = ""
    DEFAULT_MODEL: str = "gpt-4o-mini"
    DEFAULT_LLM_PROVIDER: str = "local"
    
    # Local Sentence Transformers model
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
