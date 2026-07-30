"""Explainable follow-back scoring."""

from __future__ import annotations

from typing import Iterable, Mapping


class FollowBackScorer:
    def __init__(self, topic_keywords: Iterable[str] = ()) -> None:
        self._topics = tuple(
            topic.strip().lower() for topic in topic_keywords if topic.strip()
        )

    def score(self, profile: Mapping[str, object]) -> dict[str, object]:
        score = 35
        reasons: list[str] = []
        risks: list[str] = []
        description = str(profile.get("description") or "").lower()
        metrics = profile.get("public_metrics")
        if not isinstance(metrics, dict):
            metrics = {}
        followers = int(metrics.get("followers_count", 0) or 0)
        following = int(metrics.get("following_count", 0) or 0)
        posts = int(metrics.get("tweet_count", 0) or 0)

        if description:
            score += 10
            reasons.append("profile_complete")
        else:
            score -= 10
            risks.append("empty_description")
        if bool(profile.get("verified")):
            score += 15
            reasons.append("verified_profile")
        if posts >= 10:
            score += 10
            reasons.append("established_post_history")
        elif posts < 3:
            score -= 10
            risks.append("limited_post_history")
        if followers >= 10:
            score += 5
            reasons.append("established_audience")
        if self._topics and any(topic in description for topic in self._topics):
            score += 20
            reasons.append("topic_match")
        if following >= 200 and following > max(followers * 20, 500):
            score -= 35
            risks.append("bulk_following_pattern")
        if bool(profile.get("protected")):
            score -= 5
            risks.append("protected_profile")

        score = max(0, min(100, score))
        if "bulk_following_pattern" in risks or score < 40:
            decision = "reject"
        elif score >= 65:
            decision = "recommend_follow"
        else:
            decision = "review"
        return {
            "decision": decision,
            "score": score,
            "reasons": reasons,
            "riskFlags": risks,
        }
