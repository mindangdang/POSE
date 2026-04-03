def build_current_profile(existing_summary: str | None) -> dict[str, str]:
    profile = {
        "persona": "정보 없음",
        "unconscious_taste": "데이터 부족",
        "recommendation": "데이터 부족",
    }

    if not existing_summary:
        return profile

    try:
        parts = existing_summary.split("\n\n")
        profile["persona"] = parts[0].replace("**페르소나**\n", "")
        profile["unconscious_taste"] = parts[1].replace("**나도 몰랐던 나의 취향**\n", "")
        profile["recommendation"] = parts[2].replace("**추천**\n", "")
    except Exception:
        pass

    return profile


def build_summary_text(summary_dict: dict[str, str]) -> str:
    return (
        f"**페르소나**\n{summary_dict.get('persona', '분석 불가')}\n\n"
        f"**나도 몰랐던 나의 취향**\n{summary_dict.get('unconscious_taste', '내용 없음')}\n\n"
        f"**추천**\n{summary_dict.get('recommendation', '추천 없음')}"
    )
