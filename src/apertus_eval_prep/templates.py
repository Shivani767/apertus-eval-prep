from __future__ import annotations

from typing import Any

# Llama-3 style wrapper applied to a non-Llama model. This is a realistic
# serving misconfiguration: the engine's default template is not the
# tokenizer's template.
MISMATCHED_LLAMA3 = (
    "<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
    "{user}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
)


def render_prompt(
    tokenizer: Any,
    user_text: str,
    mode: str,
    system_prompt: str | None = None,
) -> str:
    """Return the string that both backends will consume as a completion prompt.

    The serving engine must not apply a second chat template on top of this.
    """
    if mode == "none":
        if system_prompt:
            return f"{system_prompt.strip()}\n\n{user_text}"
        return user_text
    if mode == "mismatched":
        body = user_text
        if system_prompt:
            body = f"{system_prompt.strip()}\n\n{user_text}"
        return MISMATCHED_LLAMA3.format(user=body)
    if mode != "tokenizer":
        raise ValueError(f"unknown chat_template mode: {mode}")

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )
