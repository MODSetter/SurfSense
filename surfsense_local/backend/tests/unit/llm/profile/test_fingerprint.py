import pytest

from modules.llm.profile import Line, from_llamacpp, from_name, from_remote

pytestmark = pytest.mark.unit


def test_hosted_open_weights_without_a_count_are_that_vendors_flagship() -> None:
    """A published repo means open weights; nobody pays to host a small one."""
    fingerprint = from_remote(
        "z-ai/glm-5.3",
        [{"id": "z-ai/glm-5.3", "hugging_face_id": "zai-org/GLM-5.3"}],
    )

    assert fingerprint.params_b is None
    assert fingerprint.line is Line.FLAGSHIP


def test_a_row_with_no_published_repo_names_its_vendor() -> None:
    """A closed line has no public count at all, so the vendor is the only fact."""
    fingerprint = from_remote(
        "anthropic/claude-sonnet-4.5",
        [{"id": "anthropic/claude-sonnet-4.5", "hugging_face_id": None}],
    )

    assert fingerprint.vendor == "anthropic"
    assert fingerprint.line is None


def test_the_published_repo_states_a_count_the_id_leaves_out() -> None:
    """`:free` selects a routing tier, not a model, so the row is the same row."""
    fingerprint = from_remote(
        "qwen/qwen3-next:free",
        [{"id": "qwen/qwen3-next", "hugging_face_id": "Qwen/Qwen3-Next-80B-A3B"}],
    )

    assert fingerprint.params_b == 80.0


def test_an_alias_is_read_from_the_model_it_points_at() -> None:
    """An alias row holds a pointer and none of the facts it points at."""
    fingerprint = from_remote(
        "~qwen/qwen3-coder-latest",
        [
            {
                "id": "~qwen/qwen3-coder-latest",
                "alias_target": {
                    "name": "Qwen: Qwen3 Coder",
                    "slug": "qwen/qwen3-coder-480b-a35b",
                },
            },
            {
                "id": "qwen/qwen3-coder-480b-a35b",
                "hugging_face_id": "Qwen/Qwen3-Coder-480B-A35B-Instruct",
            },
        ],
    )

    assert fingerprint.params_b == 480.0
    assert fingerprint.name == "~qwen/qwen3-coder-latest"


def test_a_small_line_word_keeps_a_hosted_model_off_the_flagship_tier() -> None:
    """Vendors that dropped counts still mark their small line: mini, xs, edge."""
    fingerprint = from_remote(
        "thinkingmachines/inkling-small",
        [
            {
                "id": "thinkingmachines/inkling-small",
                "hugging_face_id": "thinkingmachines/inkling-small",
            }
        ],
    )

    assert fingerprint.line is Line.SMALL


def test_a_variant_row_that_stands_alone_still_describes_its_model() -> None:
    """Some variant ids are listed with no base row, and they carry the repo."""
    fingerprint = from_remote(
        "liquid/lfm-2.5-2.6b:free",
        [{"id": "liquid/lfm-2.5-2.6b:free", "hugging_face_id": "LiquidAI/LFM2.5-2.6B"}],
    )

    assert fingerprint.params_b == 2.6


def test_a_line_word_is_only_a_line_word_on_its_own() -> None:
    """`minimax` and `gemini` end in line words; reading them as one mis-tiers both."""
    flagship = from_remote(
        "minimax/minimax-m3",
        [{"id": "minimax/minimax-m3", "hugging_face_id": "MiniMaxAI/MiniMax-M3"}],
    )

    assert flagship.line is Line.FLAGSHIP
    assert from_name("openai_compatible", "gemini-3-pro").line is Line.FLAGSHIP


def test_a_name_from_an_endpoint_that_describes_nothing_reveals_nothing() -> None:
    """A vLLM deployment can serve any weights under any name, so nothing is assumed."""
    fingerprint = from_name("openai_compatible", "acme/internal-v2")

    assert fingerprint.params_b is None
    assert fingerprint.vendor is None
    assert fingerprint.line is None


def test_a_stated_parameter_count_is_used_exactly() -> None:
    """`GET /props` carries the real count, so nothing has to be inferred."""
    fingerprint = from_llamacpp(
        "Qwen3-8B-Q4_K_M",
        {"model_info": {"general.parameter_count": 8030261248}},
    )

    assert fingerprint.params_b == 8.0


def test_a_filename_states_the_size_when_the_runtime_does_not() -> None:
    """Quantizers put the size in the name, and it beats guessing from bytes."""
    fingerprint = from_llamacpp("Qwen3-1.7B-Q4_K_M", {})

    assert fingerprint.params_b == 1.7


def test_a_model_that_states_nothing_anywhere_stays_unknown() -> None:
    """Unknown is honest. The old blob-size division read `gemma3:4b` as 5.5B,
    because embedding tables inflate a count taken from weights alone, and a
    wrong number is worse than none: it picks the wrong prompt with confidence.
    """
    assert from_llamacpp("custom-model", {}).params_b is None


def test_total_parameters_win_over_active_ones() -> None:
    """A mixture of experts states both; the total is what the model can do."""
    fingerprint = from_name(
        "openai_compatible", "qwen/qwen3-235b-a22b-thinking-2507:free"
    )

    assert fingerprint.params_b == 235.0
