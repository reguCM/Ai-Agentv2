"""固定入力。Gemma 一次ログから抽出。人間補正なし。既存実験は import しない。"""

KNOWN = ["main.py", "helper.py", "config.py", "tests/test_main.py"]

# 指示書 Case A–E / 回帰用の短い固定文
CASE_A_READ_HELPER = "helper.pyを読む"
CASE_B_PATCH_NO_FILE = "FIELD_COUNTを3に変更する"
CASE_C_OPEN_MODIFY_RUN = "Open / Modify / Run your tests"
CASE_D_RUN_TEST_AGAIN = "Testをもう一度実行する"
CASE_E_FENCE_TOKENS = (
    "helper.pyを読む。\n"
    "```python\n"
    "READY = True\n"
    "TEST = False\n"
    "READ = 1\n"
    "```\n"
)

CONFIRM_CONFIG = "config.pyを確認する"
SEARCH_FIELD_COUNT = "FIELD_COUNTを探す"
AMBIGUOUS_FIX = "修正してください。"
AMBIGUOUS_CHECK = "確認してください。"
AMBIGUOUS_LOOK = "調べてください。"
AMBIGUOUS_THERE = "そこを直してください。"

MULTI_READ_THEN_TEST = (
    "helper.pyを読んでください。\n"
    "その後config.pyを確認してください。\n"
    "最後にTestしてください。"
)
ORDER_MAIN_THEN_HELPER = "main.pyを見てからhelper.pyを確認したい"
MISSING_FILE = "missing_no_such.pyを読む"
READY_NOT_READ = "The test is READY and should run again."
RUN_THE_TESTS_AGAIN = "Run the tests again."
SENTENCE_SEQUENCE = (
    "helper.pyを読みます。\n"
    "その後、FIELD_COUNTを確認します。\n"
    "問題があれば修正します。\n"
    "最後にTestを実行します。"
)
READ_THEN_PATCH_NAMED = (
    "config.pyを確認する。その後config.pyのFIELD_COUNTを3に変更する。"
)
PATCH_THEN_TEST = (
    "config.pyのFIELD_COUNTを3に変更する。その後Testをもう一度実行する。"
)

# 一次資料: judgment_layer_llm_connection_experiment/results/20260901T033113Z/gemma3_12b/run.json
GEMMA_SOURCE = (
    "research/llm_benchmarks/judgment_layer_llm_connection_experiment"
    "/results/20260901T033113Z/gemma3_12b/run.json"
)
GEMMA_T4_RAW = (
    "You are absolutely correct. That explains everything.\n"
    "\n"
    "With `FIELD_COUNT = 1` in `config.py`, the `load_items` function returns "
    '`LABELS[:1]`, which is `["alpha"]`. This list has only one element, so '
    "accessing `items[2]` in `assemble` results in the `IndexError`.\n"
    "\n"
    "**The definitive solution is to change `config.py` to:**\n"
    "\n"
    "```python\n"
    "FIELD_COUNT = 3\n"
    "READY = False\n"
    "```\n"
    "\n"
    "This will ensure that `load_items` returns a list with at least three "
    'elements (`["alpha", "beta", "gamma"]`), preventing the `IndexError`.\n'
    "\n"
    "I apologize for the previous, partially correct suggestions. I was focusing "
    "on the code itself without fully understanding the role of the `config.py` "
    "file and the value of `FIELD_COUNT`.  Your providing the contents of "
    "`config.py` was crucial to identifying the true root cause.\n"
    "\n"
    "Now, after making this change to `config.py`, re-run your tests and the "
    "`main.py` script. The problem should be completely resolved."
)
GEMMA_T5_RAW = (
    "You are absolutely right to call me out on that. My apologies. I got caught "
    "up in explaining the solution and completely missed the instruction to "
    "provide an executable action.\n"
    "\n"
    "**Executable Action:**\n"
    "\n"
    "1.  **Open the `config.py` file.**\n"
    "2.  **Modify the line `FIELD_COUNT = 1` to `FIELD_COUNT = 3`.**\n"
    "3.  **Save the `config.py` file.**\n"
    "4.  **Run your tests and `main.py` again.**\n"
    "\n"
    "That's the single, actionable step to resolve the issue. I am working on "
    "improving my ability to follow instructions more precisely. Thank you for "
    "pointing out my oversight."
)

CYCLE_TEXTS = [
    CASE_A_READ_HELPER,
    SEARCH_FIELD_COUNT,
    CASE_B_PATCH_NO_FILE,
    CASE_D_RUN_TEST_AGAIN,
    "config.pyのREADYをTrueに変更する。",
    CASE_D_RUN_TEST_AGAIN,
]
