from __future__ import annotations

from pathlib import Path


def main() -> None:
    target = Path(
        "/usr/local/lib/python3.11/site-packages/mineru/model/mfr/"
        "unimernet/unimernet_hf/unimer_mbart/modeling_unimer_mbart.py"
    )
    if not target.exists():
        print(f"MinerU UnimerMBart patch skipped; file not found: {target}")
        return

    text = target.read_text(encoding="utf-8")
    changed = False

    if "cache_position: Optional[torch.LongTensor] = None" not in text:
        needle = "        count_gt: Optional[torch.LongTensor] = None,\n"
        replacement = (
            needle
            + "        cache_position: Optional[torch.LongTensor] = None,\n"
        )
        if needle not in text:
            raise RuntimeError("MinerU UnimerMBart forward signature changed; cache_position patch not applied")
        text = text.replace(needle, replacement, 1)
        changed = True

    cache_needle = "        # past_key_values_length\n        past_key_values_length = past_key_values[0][0].shape[2] if past_key_values is not None else 0\n"
    cache_replacement = """        # past_key_values_length
        if past_key_values is not None and hasattr(past_key_values, "to_legacy_cache"):
            past_key_values = past_key_values.to_legacy_cache()
        if past_key_values is not None and len(past_key_values) == 0:
            past_key_values = None
        if past_key_values is not None and past_key_values[0][0] is not None:
            past_key_values_length = past_key_values[0][0].shape[2]
        else:
            past_key_values_length = 0
"""
    if cache_replacement not in text:
        if cache_needle not in text:
            raise RuntimeError("MinerU UnimerMBart decoder cache logic changed; cache compatibility patch not applied")
        text = text.replace(cache_needle, cache_replacement, 1)
        changed = True

    if changed:
        target.write_text(text, encoding="utf-8")
        print("MinerU UnimerMBart transformers cache compatibility patch applied")
    else:
        print("MinerU UnimerMBart transformers cache compatibility patch already applied")


if __name__ == "__main__":
    main()
