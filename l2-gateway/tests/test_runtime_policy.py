import unittest

from app.runtime_policy import RuntimePolicy


class RuntimePolicyTests(unittest.TestCase):
    def test_m2_policy_restricts_model_and_generation_limits(self):
        policy = RuntimePolicy.from_mapping(
            {
                "IRIS_RUNTIME_PROFILE": "m2",
                "IRIS_DEFAULT_MODEL": "qwen3.5:4b",
                "IRIS_ALLOWED_MODELS": "qwen3.5:4b",
                "IRIS_MODEL_NUM_CTX": "8192",
                "IRIS_MODEL_NUM_PREDICT": "1024",
            }
        )

        self.assertEqual(policy.resolve_model("qwen3.5:4b"), "qwen3.5:4b")
        with self.assertRaisesRegex(ValueError, "not allowed"):
            policy.resolve_model("qwen3:30b")

        options = policy.apply_generation_limits(
            {"num_ctx": 32768, "num_predict": 4096, "temperature": 0.4}
        )
        self.assertEqual(options["num_ctx"], 8192)
        self.assertEqual(options["num_predict"], 1024)
        self.assertEqual(options["temperature"], 0.4)

    def test_empty_allowlist_keeps_all_models(self):
        policy = RuntimePolicy.from_mapping({})
        models = [{"name": "a"}, {"name": "b"}]

        self.assertEqual(policy.filter_ollama_models(models), models)

    def test_allowlist_filters_ollama_model_catalog(self):
        policy = RuntimePolicy.from_mapping(
            {"IRIS_ALLOWED_MODELS": "qwen3.5:4b,gemma3:4b"}
        )
        models = [
            {"name": "qwen3.5:4b"},
            {"name": "qwen3:30b"},
            {"name": "gemma3:4b"},
        ]

        self.assertEqual(
            [model["name"] for model in policy.filter_ollama_models(models)],
            ["qwen3.5:4b", "gemma3:4b"],
        )

    def test_invalid_limits_fall_back_to_bounded_defaults(self):
        policy = RuntimePolicy.from_mapping(
            {
                "IRIS_MODEL_NUM_CTX": "invalid",
                "IRIS_MODEL_NUM_PREDICT": "999999",
            }
        )

        self.assertEqual(policy.max_context_tokens, 32768)
        self.assertEqual(policy.max_output_tokens, 32768)


if __name__ == "__main__":
    unittest.main()
