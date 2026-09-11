"""
Context Engine: Assembles and sizes the prompt context dynamically.
Combines Core Identity, Long-term Memories, Conversation History, and Current Query,
intelligently pruning history if context limits are approached.
"""
from typing import List, Dict, Any, Optional
from core.identity.identity_manager import identity_manager
from core.context.token_counter import estimate_tokens, estimate_messages_tokens
from database.models.message import Message
from database.models.memory import Memory


class ContextBuilder:
    """Constructs token-budget-aware prompts for model execution."""

    def __init__(
        self,
        default_max_context_tokens: int = 16000,
        reserved_output_tokens: int = 2048,
    ):
        self.default_max_context_tokens = default_max_context_tokens
        self.reserved_output_tokens = reserved_output_tokens

    def build_context(
        self,
        user_message: str,
        conversation_history: List[Message],
        memories: Optional[List[Memory]] = None,
        agent_instructions: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        context_limit: Optional[int] = None,
        max_history_turns: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Builds a prioritized, token-capped message list for LLM consumption.
        """
        limit = context_limit or self.default_max_context_tokens
        output_reserve = min(self.reserved_output_tokens, max(50, limit // 4))
        available_budget = max(50, limit - output_reserve)

        # 1. Format memory block
        memory_text = ""
        if memories:
            memory_lines = ["[PERSISTENT MEMORY / KNOWN USER FACTS]"]
            for m in memories:
                memory_lines.append(f"- [{m.category.upper()}] {m.key}: {m.value}")
            memory_text = "\n".join(memory_lines)

        # 2. Build master system prompt
        system_content = identity_manager.get_system_prompt(
            agent_instructions=agent_instructions,
            custom_instructions=custom_instructions,
        )
        if memory_text:
            system_content = f"{system_content}\n\n{memory_text}"

        system_msg = {"role": "system", "content": system_content}
        current_user_msg = {"role": "user", "content": user_message}

        system_tokens = estimate_tokens(system_content) + 6
        user_tokens = estimate_tokens(user_message) + 6
        mandatory_tokens = system_tokens + user_tokens

        # If mandatory tokens exceed entire budget, truncate user query gracefully
        history_budget = max(0, available_budget - mandatory_tokens)

        # 3. Assemble history messages
        history_msgs: List[Dict[str, Any]] = []
        recent_history = conversation_history[-max_history_turns:] if conversation_history else []

        # Prune from oldest to newest if budget is tight
        for msg in reversed(recent_history):
            item = {"role": msg.role, "content": msg.content}
            cost = estimate_tokens(msg.content) + 6
            if cost <= history_budget:
                history_msgs.insert(0, item)
                history_budget -= cost
            else:
                # Can't fit older messages within budget
                break

        # 4. Return final combined sequence
        return [system_msg] + history_msgs + [current_user_msg]


context_builder = ContextBuilder()
