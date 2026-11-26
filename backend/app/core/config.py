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
    LLM_ENGINE: str = "ollama"  # ollama | llama_cpp | vllm | auto
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LOCAL_MODEL: str = "qwen2.5:3b"
    LLAMA_CPP_BASE_URL: str = ""  # e.g. http://127.0.0.1:8081/v1
    LLAMA_CPP_MODEL: str = "local-gguf"
    VLLM_BASE_URL: str = ""       # e.g. http://127.0.0.1:8001/v1
    VLLM_MODEL: str = "Qwen/Qwen2.5-3B-Instruct"
    
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"
    DEFAULT_MODEL: str = "gpt-4o-mini"
    DEFAULT_LLM_PROVIDER: str = "local"
    
    # Local Sentence Transformers model
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"]
    RATE_LIMIT_PER_MINUTE: int = 180
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150

    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
