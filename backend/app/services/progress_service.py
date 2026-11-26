from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.agents.analytics_agent import AnalyticsAgent
from app.schemas.learning_tools import ProgressResponse


class ProgressService:
    @staticmethod
    async def get_user_progress(db: AsyncSession, user_id: int) -> ProgressResponse:
        metrics = await AnalyticsAgent.analyze_user_learning(db, user_id)
        return ProgressResponse(**metrics)
