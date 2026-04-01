import anthropic
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def parse_claude_json(text):
    clean = text.strip()
    if "```" in clean:
        parts = clean.split("```")
        clean = parts[1] if len(parts) > 1 else clean
        if clean.startswith("json"): clean = clean[4:]
    clean = clean.strip()
    clean = re.sub(r',\s*([}\]])', r'\1', clean)
    return json.loads(clean)

def load_recent_insights():
    """Load the most recent feed and story insights files."""
    insights_dir = "data/insights"
    if not os.path.exists(insights_dir):
        return {}, {}

    feed_files  = sorted([f for f in os.listdir(insights_dir)
                          if not f.startswith("stories_")
                          and f.endswith(".json")])
    story_files = sorted([f for f in os.listdir(insights_dir)
                          if f.startswith("stories_")
                          and f.endswith(".json")])

    feed_insights  = load_json(f"{insights_dir}/{feed_files[-1]}")  \
                     if feed_files  else {}
    story_insights = load_json(f"{insights_dir}/{story_files[-1]}") \
                     if story_files else {}

    return feed_insights, story_insights

def build_performance_summary(analysis, feed_insights, story_insights):
    """Build a readable performance summary for the Claude prompt."""
    lines = []

    feed_records  = analysis.get("feed_record_count", 0)
    story_records = analysis.get("story_record_count", 0)

    lines.append(f"Feed posts analysed: {feed_records}")
    lines.append(f"Story posts analysed: {story_records}")

    # Feed model insights
    feed_model = analysis.get("feed_model", {})
    if feed_model.get("phase") != "bootstrap":
        lines.append(f"\nFeed model phase: {feed_model.get('phase')}")
        lines.append(f"Feed model MAE: {feed_model.get('mae', 'N/A')}")
        for i in feed_model.get("insights", []):
            lines.append(f"  • {i}")
    else:
        lines.append(f"\nFeed model: bootstrap phase ({feed_records}/20 posts)")

    # Format stats
    fmt_stats = analysis.get("format_stats", {})
    if fmt_stats:
        lines.append("\nPerformance by content type:")
        for fmt, s in fmt_stats.items():
            lines.append(f"  {fmt}: eng={s.get('avg_engagement_rate',0):.2%} "
                         f"save={s.get('avg_save_rate',0):.2%} "
                         f"(n={s.get('count',0)})")

    # Timing stats
    timing = analysis.get("timing_stats", {})
    if timing:
        lines.append(f"\nBest posting day: {timing.get('best_day','')}")
        lines.append(f"Best posting hour UTC: {timing.get('best_hour_utc','')}")

    # Story model insights
    story_model = analysis.get("story_model", {})
    if story_model.get("phase") != "bootstrap":
        lines.append(f"\nStory model phase: {story_model.get('phase')}")
        lines.append(f"Story model MAE: {story_model.get('mae', 'N/A')}")
        for i in story_model.get("insights", []):
            lines.append(f"  • {i}")
    else:
        lines.append(f"\nStory model: bootstrap phase ({story_records}/20 stories)")

    # Story type stats
    story_stats = analysis.get("story_stats", {})
    if story_stats:
        lines.append("\nPerformance by story type:")
        for st, s in story_stats.items():
            lines.append(f"  {st}: completion={s.get('avg_completion_rate',0):.2%} "
                         f"interaction={s.get('avg_interaction_rate',0):.2%} "
                         f"(n={s.get('count',0)})")

    # Account summary
    account = feed_insights.get("account", {})
    if account:
        lines.append(f"\nAccount followers: {account.get('followers_count',0)}")
        lines.append(f"Total posts published: {account.get('media_count',0)}")

    return "\n".join(lines)

def generate_updated_strategy(client, current_strategy, performance_summary,
                               feed_records, story_records):
    """Ask Claude to rewrite strategy.json based on performance data."""

    phase = "bootstrap"
    if feed_records >= 100: phase = "xgboost"
    elif feed_records >= 50: phase = "bayesian"
    elif feed_records >= 20: phase = "ridge"

    prompt = f"""You are the strategy optimiser for @ask.claudeai — an Instagram automation bot posting Claude API tips for developers.

CURRENT STRATEGY:
{json.dumps(current_strategy, indent=2)}

PERFORMANCE DATA THIS WEEK:
{performance_summary}

YOUR TASK:
Analyse the performance data and update the strategy.json to improve future content.

RULES:
- Only update values where the data supports the change
- If in bootstrap phase (under 20 posts), keep most defaults — only make conservative adjustments
- Never remove existing hashtags from evergreen_tags — only add new ones
- Confidence scores must be between 0.0 and 1.0
- Keep the exact same JSON structure and all existing keys
- Increment posts_in_dataset by the number of new feed records
- Increment stories_in_dataset by the number of new story records
- Update model_phase to: {phase}
- Update schema_version timestamp

Return ONLY the complete updated strategy.json as valid JSON. No explanation, no markdown, just the JSON object."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_claude_json(message.content[0].text)

def generate_weekly_report(client, current_strategy, new_strategy,
                            performance_summary, analysis,
                            feed_insights, story_insights):
    """Ask Claude to write the weekly narrative report."""

    prompt = f"""You are writing the weekly performance report for @ask.claudeai — a Claude API tips Instagram account.

PERFORMANCE DATA:
{performance_summary}

Write a clear, actionable weekly report covering:
1. What worked well this week (feed posts + stories)
2. What underperformed and why
3. Top 5 prioritised suggestions for next week (tag each as [feed] or [story])
4. One thing to test next week as an experiment

Keep it practical and specific. Under 400 words total.

Return ONLY valid JSON:
{{
  "narrative": "your weekly narrative here (2-3 paragraphs)",
  "suggestions": [
    {{"priority": 1, "channel": "feed", "suggestion": "specific actionable suggestion", "confidence": 0.85}},
    {{"priority": 2, "channel": "story", "suggestion": "specific actionable suggestion", "confidence": 0.72}},
    {{"priority": 3, "channel": "feed", "suggestion": "suggestion", "confidence": 0.68}},
    {{"priority": 4, "channel": "story", "suggestion": "suggestion", "confidence": 0.61}},
    {{"priority": 5, "channel": "feed", "suggestion": "suggestion", "confidence": 0.55}}
  ],
  "experiment": "one specific A/B test to run next week",
  "strategy_changes_applied": [],
  "strategy_changes_deferred": []
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_claude_json(message.content[0].text)

def diff_strategy(old, new):
    """Find what changed between old and new strategy."""
    changes_applied  = []
    changes_deferred = []

    def compare(old_v, new_v, path=""):
        if isinstance(old_v, dict) and isinstance(new_v, dict):
            for k in set(list(old_v.keys()) + list(new_v.keys())):
                compare(old_v.get(k), new_v.get(k), f"{path}.{k}")
        elif isinstance(old_v, list) and isinstance(new_v, list):
            if old_v != new_v:
                changes_applied.append(f"{path}: {old_v} → {new_v}")
        else:
            if old_v != new_v and path:
                changes_applied.append(f"{path}: {old_v} → {new_v}")

    compare(old, new)
    return changes_applied, changes_deferred

def optimize_strategy():
    print("=" * 50)
    print("Optimising strategy")
    print("=" * 50)

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # Load all inputs
    current_strategy = load_json("data/strategy.json")
    analysis         = load_json("data/model/analysis_results.json")
    feed_insights, story_insights = load_recent_insights()

    feed_records  = analysis.get("feed_record_count", 0)
    story_records = analysis.get("story_record_count", 0)

    print(f"\nFeed records:  {feed_records}")
    print(f"Story records: {story_records}")

    # Build performance summary
    performance_summary = build_performance_summary(
        analysis, feed_insights, story_insights)
    print(f"\nPerformance summary:\n{performance_summary}")

    # Generate updated strategy
    print("\nGenerating updated strategy...")
    try:
        new_strategy = generate_updated_strategy(
            client, current_strategy, performance_summary,
            feed_records, story_records)
        print("Strategy updated successfully")
    except Exception as e:
        print(f"Strategy generation failed: {e}")
        new_strategy = current_strategy
        new_strategy["meta"]["last_updated"] = datetime.now().isoformat()

    # Find what changed
    changes_applied, changes_deferred = diff_strategy(
        current_strategy, new_strategy)
    print(f"\nChanges applied: {len(changes_applied)}")
    for c in changes_applied[:10]:
        print(f"  {c}")

    # Save new strategy
    save_json("data/strategy.json", new_strategy)
    print("\nstrategy.json updated")

    # Generate weekly report
    print("\nGenerating weekly report...")
    try:
        report_data = generate_weekly_report(
            client, current_strategy, new_strategy,
            performance_summary, analysis,
            feed_insights, story_insights)
    except Exception as e:
        print(f"Report generation failed: {e}")
        report_data = {
            "narrative": "Report generation failed.",
            "suggestions": [],
            "experiment": "",
            "strategy_changes_applied": changes_applied,
            "strategy_changes_deferred": changes_deferred
        }

    # Add change log to report
    report_data["strategy_changes_applied"]  = changes_applied
    report_data["strategy_changes_deferred"] = changes_deferred

    # Save weekly report
    date_str     = datetime.now().strftime("%Y-%m-%d")
    report_path  = f"data/reports/{date_str}_weekly_report.json"

    report = {
        "generated_at":    datetime.now().isoformat(),
        "week_ending":     date_str,
        "feed_records":    feed_records,
        "story_records":   story_records,
        "performance":     performance_summary,
        "feed_model":      analysis.get("feed_model", {}),
        "story_model":     analysis.get("story_model", {}),
        **report_data
    }

    save_json(report_path, report)
    print(f"Weekly report saved: {report_path}")

    # Print suggestions
    print("\nTop suggestions for next week:")
    for s in report_data.get("suggestions", []):
        conf = s.get("confidence", 0)
        flag = "✓" if conf >= 0.70 else "~"
        print(f"  {flag} [{s.get('channel','').upper()}] "
              f"P{s.get('priority','?')}: {s.get('suggestion','')}")

    print(f"\nExperiment: {report_data.get('experiment','')}")
    print("\n" + "=" * 50)
    print("Optimisation complete")
    print("=" * 50)

    return report

if __name__ == "__main__":
    optimize_strategy()