"""Generate v0 intentional cases (observation dataset). No ground-truth judgment labels."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "cases.json"

cases: list[dict] = []


def add(
    case_id: str,
    category: str,
    request: str,
    observe_goal: str,
    *,
    group_id: str | None = None,
):
    item = {
        "id": case_id,
        "category": category,
        "request": request,
        "observe_goal": observe_goal,
    }
    if group_id:
        item["group_id"] = group_id
    cases.append(item)


# --- A Web必要・明確 ---
add("A01", "web_needed_clear", "今日の日本の主なニュースを教えて", "時事・最新情報でWeb判断が出るか")
add("A02", "web_needed_clear", "現在のドル円の大まかな為替水準について教えて", "現在価格・相場系")
add("A03", "web_needed_clear", "OpenAIについて最近何か大きな発表はありましたか", "最近の出来事")
add("A04", "web_needed_clear", "今のNVIDIAの株価の雰囲気を教えて", "現在の企業状況")
add("A05", "web_needed_clear", "明日の大阪の天気を教えて", "予報・外部情報")
add("A06", "web_needed_clear", "Python 3.13で追加された主な変更点を教えて", "版固有の外部情報")

# --- B Web不要・明確 ---
add("B01", "web_unneeded_clear", "CPU使用率を教えて", "ローカル観測Tool")
add("B02", "web_unneeded_clear", "GPUの状態を教えて", "ローカル観測Tool")
add("B03", "web_unneeded_clear", "registry/tools.json を読んで visibility が agent のTool名を一覧して", "File Tool")
add("B04", "web_unneeded_clear", "docs/v1_basic_specification.md の冒頭にあるV1の目的を要約して", "ローカル文書")
add("B05", "web_unneeded_clear", "Pythonのリストとタプルの違いを簡単に説明して", "一般知識")
add("B06", "web_unneeded_clear", "このリポジトリ直下にどんな主要フォルダがあるか list して", "list_files")

# --- C Web必要・曖昧 ---
add("C01", "web_needed_ambiguous", "WindowsのCPU温度取得って最近どうなってる？", "曖昧な『最近』")
add("C02", "web_needed_ambiguous", "Ollamaについて詳しく教えて", "詳しく＝Webか知識か曖昧")
add("C03", "web_needed_ambiguous", "RTX 3060って今どういう扱いですか？", "『今』の扱いが曖昧")
add("C04", "web_needed_ambiguous", "ローカルLLMの事情、最近どう？", "事情が広い")
add("C05", "web_needed_ambiguous", "この手のエージェントって今どこまで実用的なの", "評価が文脈依存")

# --- D Web語ありだが実質Web不要 ---
add("D01", "web_word_but_unneeded", "このプロジェクトのWeb検索Toolの実装を、ローカルのコードから説明して", "『Web検索』語＋ローカル説明")
add("D02", "web_word_but_unneeded", "registryにある最新のTool一覧をファイルから確認して", "『最新』語＋ローカル")
add("D03", "web_word_but_unneeded", "現在のagent公開Toolは何か、tools.jsonを読んで答えて", "『現在』語＋ローカル")
add("D04", "web_word_but_unneeded", "ニュースという単語がdocsに出てくるか、リポジトリ内を検索して", "『ニュース』語＋search_files")
add("D05", "web_word_but_unneeded", "検索結果のJSON形式がコード上どうなっているか、実装を読んで説明して", "『検索結果』語＋read")

# --- E Web語なしだが実質外部情報向き ---
add("E01", "web_needed_no_web_words", "岸田政権以降の防衛費議論でよく挙げられる論点を整理して", "明示語なし・時事")
add("E02", "web_needed_no_web_words", "ChatGPTの有料プランの違いを教えて", "製品情報・明示『検索』なし")
add("E03", "web_needed_no_web_words", "東京都のごみ分別の基本ルールを教えて", "地域実務情報")
add("E04", "web_needed_no_web_words", "鉄道の遅延証明書は一般にどう発行されるか教えて", "実務手続き")
add("E05", "web_needed_no_web_words", "Appleの次の大型発表イベントはいつ頃と言われているか教えて", "予定・噂の外部情報")

# --- F 検索困難 ---
add("F01", "search_hard", "zxqwv-nonexistent-topic-9f3a2b1c の公式発表日を教えて。分からなければその旨を書いて", "存在しない話題")
add("F02", "search_hard", "架空の企業 Quiblaxor Dynamics の2023年売上を教えて", "架空固有名詞")
add("F03", "search_hard", "個人ブログ『みどりのティーカップ日記』の第137話の要約を教えて", "極端にニッチ")
add("F04", "search_hard", "同じ出来事について日本語と英語で報じ方の違いを、根拠を分けて比較して", "複数情報源照合が重い")
add("F05", "search_hard", "2010年ごろのローカル掲示板にだけ載っていた某ツールの使い方を再現して", "古い・入手困難")

# --- G 既存Toolで解決可能 ---
add("G01", "existing_tool_ok", "GPUを使っているプロセスがあれば一覧して", "get_gpu_processes")
add("G02", "existing_tool_ok", "config/pipeline.yaml の active_model をファイルから確認して", "read_file")
add("G03", "existing_tool_ok", "tools/system 配下で execution_identity という名前のファイルを探して", "search_files")
add("G04", "existing_tool_ok", "CPUの状態を確認して短く報告して", "cpu_status")
add("G05", "existing_tool_ok", "registry フォルダ直下のファイル名を列挙して", "list_files")

# --- G' 新Toolが必要そう（正解ラベルではない） ---
add("G06", "tool_gap_candidate", "キーボードのバッテリー残量を取得したい", "観測対象の不足候補")
add("G07", "tool_gap_candidate", "接続中のBluetoothデバイスの電波強度を数値で出したい", "不足候補")
add("G08", "tool_gap_candidate", "マイク入力のリアルタイム音量ピークを返す機能が欲しい", "不足候補")
add("G09", "tool_gap_candidate", "母艦のUPS残量パーセントを取得したい", "不足候補")
add("G10", "tool_gap_candidate", "ファン回転数を読む機能が欲しい", "不足候補")

# --- H 複数Tool ---
add("H01", "composite_multi_tool", "docs/v1_basic_specification.md のV1目的をファイルから確認し、同様のテーマの一般説明も外部情報で補って比較して", "File→Web寄り")
add("H02", "composite_multi_tool", "GPUの状態を確認したうえで、同世代GPUの一般的な消費電力の目安も調べて並べて", "GPU→Web")
add("H03", "composite_multi_tool", "agent_tool_gate の実装方針をコードから読み、同様の『デフォルト確認』の一般的な設計議論も参照して整理して", "File→Web")

# --- 言い換えグループ（意味を維持） ---
gid_weather = "para_osaka_weather"
add("P01a", "paraphrase", "大阪の明日の天気を教えて", "言い換え:天気", group_id=gid_weather)
add("P01b", "paraphrase", "明日、大阪は雨ですか？", "言い換え:天気", group_id=gid_weather)
add("P01c", "paraphrase", "明日大阪に行くんですが、傘は必要そうですか？", "言い換え:天気", group_id=gid_weather)

gid_rtx = "para_rtx3060"
add("P02a", "paraphrase", "RTX 3060について教えて", "言い換え:RTX", group_id=gid_rtx)
add("P02b", "paraphrase", "今のRTX 3060の立ち位置を教えて", "言い換え:RTX", group_id=gid_rtx)

assert len(cases) == 50, len(cases)

payload = {
    "version": "v0",
    "purpose": (
        "PROJECT_AGENT judgment-tendency observation. "
        "No ground-truth correctness labels. Not for scoring agent quality."
    ),
    "principles": [
        "observe before improve",
        "do not embed gold judgments",
        "do not change heuristic for collection",
        "Stage3 misjudgment labels stay null",
    ],
    "case_count": len(cases),
    "cases": cases,
}

OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {len(cases)} cases -> {OUT}")
cats: dict[str, int] = {}
for c in cases:
    cats[c["category"]] = cats.get(c["category"], 0) + 1
print(json.dumps(cats, ensure_ascii=False, indent=2))
