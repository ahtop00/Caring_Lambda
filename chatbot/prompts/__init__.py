# chatbot/prompts/__init__.py

from .search import get_search_prompt
from .reframing import get_reframing_prompt
from .report import get_report_prompt
from .mind_diary import get_mind_diary_prompt

__all__ = ['get_search_prompt', 'get_reframing_prompt', 'get_mind_diary_prompt', 'get_report_prompt']
