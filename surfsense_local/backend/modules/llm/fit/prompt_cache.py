"""How much host memory llama-server may keep earlier prompts in.

Chat, Studio and the agent share the runtime's few slots. When a slot goes to
another request, the prompt it held is saved in RAM and read back when its
caller returns, rather than being read again from the start.
"""

from modules.llm.fit.budget import HardwareBudget

# llama.cpp's own `cache_ram_mib` at b11050 (common/common.h): what a model gets
# when nothing says otherwise.
LLAMA_CPP_PROMPT_CACHE_MIB = 8192

# Earlier prompts may take this share of what the machine can give a model, so
# on a small machine they cannot crowd out the model that reads them.
PROMPT_CACHE_SHARE = 0.25

_MIB = 1024 * 1024


def prompt_cache_mib(budget: HardwareBudget) -> int:
    """A quarter of the memory a model may use here, never above llama.cpp's own size."""
    if budget.ram_available_bytes <= 0:
        # Nothing read the memory; turning the cache off would cost every caller.
        return LLAMA_CPP_PROMPT_CACHE_MIB
    share = int(budget.ram_available_bytes * PROMPT_CACHE_SHARE) // _MIB
    return min(LLAMA_CPP_PROMPT_CACHE_MIB, share)
