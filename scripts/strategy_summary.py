import json
import os

def get_strategy_summary(strategy_path="data/strategy.json"):
    """
    Return a compact ~200-token summary of strategy.json
    instead of injecting the full 800-token file into every prompt.
    """
    if not os.path.exists(strategy_path):
        return "Strategy: bootstrap phase. Post Claude API tips 3x/week."

    with open(strategy_path, "r") as f:
        s = json.load(f)

    meta    = s.get("meta", {})
    timing  = s.get("timing", {})
    fmt     = s.get("content_format", {})
    topics  = s.get("topics", {})
    hooks   = s.get("hooks", {})
    caption = s.get("caption", {})
    hashtags= s.get("hashtags", {})

    # Top topic clusters
    clusters = [c["cluster"] for c in topics.get("ranked_clusters", [])[:3]]
    trending = topics.get("trending_boost", [])[:2]
    avoid    = topics.get("always_avoid", [])[:2]

    # Best format weights
    weights = fmt.get("format_weights", {})
    best_fmt = max(weights, key=weights.get) if weights else "reel"

    # Best timing
    days  = [d["day"] for d in timing.get("preferred_days", [])[:2]]
    hours = timing.get("preferred_hours_utc", [13])[:2]

    # Evergreen tags
    evergreen = hashtags.get("evergreen_tags", [])[:5]

    summary = f"""STRATEGY SUMMARY (phase: {meta.get('model_phase','bootstrap')}, posts: {meta.get('posts_in_dataset',0)})
TOP TOPICS: {', '.join(clusters)}
TRENDING NOW: {', '.join(trending) if trending else 'none'}
AVOID: {', '.join(avoid) if avoid else 'none'}
BEST FORMAT: {best_fmt} ({int(weights.get(best_fmt,0)*100)}% weight)
HOOK STYLES: reel={hooks.get('by_format',{}).get('reel','bold_statement')}, carousel={hooks.get('by_format',{}).get('carousel','number_list')}, static={hooks.get('by_format',{}).get('static','how_to')}
TIMING: {', '.join(days)} at {', '.join(str(h)+':00' for h in hours)} UTC
CAPTION: {caption.get('optimal_word_count',{}).get('static',{}).get('min',80)}-{caption.get('optimal_word_count',{}).get('static',{}).get('max',150)} words, {caption.get('cta_style','save_prompt')} CTA, {caption.get('emoji_density','light')} emoji
HASHTAGS ({hashtags.get('total_count',18)} total): {' '.join(evergreen)}
COOLDOWN: {topics.get('topic_cooldown_days',14)} days between same topics"""

    return summary

if __name__ == "__main__":
    print(get_strategy_summary())