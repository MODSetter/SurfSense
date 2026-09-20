"""Architectures llama.cpp can run.

The gate is the header, not Hugging Face's tags. Counted on `library=gguf`, the
pipeline tags cover roughly 43,500 of 204,797 repos, so **about 80% carry no
useful tag at all** and filtering by tag would hide four fifths of the catalog,
including working chat models whose uploader left the field blank.

Two header facts do the job structurally instead: a supported architecture
excludes Whisper-shaped models, and a present chat template excludes embedding
models.
"""

# LLM_ARCH_* in llama.cpp. Kept as data rather than fetched, because the app is
# airgapped and this list changes only when the pinned build does.
SUPPORTED = frozenset(
    {
        "llama", "llama4", "deci", "falcon", "falcon-h1", "grok", "gpt2", "gptj",
        "gptneox", "mpt", "baichuan", "starcoder", "refact", "bert", "nomic-bert",
        "nomic-bert-moe", "neo-bert", "jina-bert-v2", "jina-bert-v3", "bloom",
        "stablelm", "qwen", "qwen2", "qwen2moe", "qwen2vl", "qwen3", "qwen3moe",
        "qwen3vl", "qwen3vlmoe", "qwen3next", "phi2", "phi3", "phimoe", "plamo",
        "plamo2", "codeshell", "orion", "internlm2", "minicpm", "minicpm3",
        "gemma", "gemma2", "gemma3", "gemma3n", "gemma-embedding", "starcoder2",
        "mamba", "mamba2", "jamba", "xverse", "command-r", "cohere2",
        "dbrx", "olmo", "olmo2", "olmoe", "openelm", "arctic", "deepseek",
        "deepseek2", "deepseek-v4", "chatglm", "glm4", "glm4moe", "bitnet",
        "t5", "t5encoder", "jais", "nemotron", "nemotron-h", "exaone", "exaone4",
        "rwkv6", "rwkv6qwen2", "rwkv7", "arwkv7", "granite", "granite-moe",
        "granite-hybrid", "chameleon", "wavtokenizer-dec", "plm", "bailingmoe",
        "bailingmoe2", "dots1", "arcee", "ernie4_5", "ernie4_5-moe", "hunyuan-moe",
        "hunyuan-dense", "smollm3", "openai-moe", "lfm2", "lfm2moe", "smallthinker",
        "dream", "seed_oss", "grovemoe", "apertus", "minimax-m2", "cogvlm",
        "pangu-embedded", "affine", "mistral", "mixtral", "solar", "stablelm2",
        "internvl", "megrez", "gpt-oss", "seed-oss", "ling", "kimi-k2",
    }
)


def is_supported(architecture: str) -> bool:
    """Unknown means not installable: no amount of memory helps."""
    return architecture.lower() in SUPPORTED
