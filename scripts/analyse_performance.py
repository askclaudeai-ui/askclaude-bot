import json
import os
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else []
    with open(path, "r") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# ═══════════════════════════════════════════════════════════════════════
# Feature engineering
# ═══════════════════════════════════════════════════════════════════════

DAY_MAP  = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,
            "friday":4,"saturday":5,"sunday":6}
TYPE_MAP = {"static":0,"carousel":1,"reel":2}
HOOK_MAP = {"how_to":0,"number_list":1,"bold_statement":2,
            "question":3,"contrarian":4}

def encode_feed_record(r):
    """Convert a training record into a feature vector."""
    return {
        "content_type_enc":  TYPE_MAP.get(r.get("content_type","static"), 0),
        "publish_day_enc":   DAY_MAP.get(r.get("publish_day","monday"), 0),
        "publish_hour":      r.get("publish_hour", 13),
        "hook_style_enc":    HOOK_MAP.get(r.get("hook_style","how_to"), 0),
        "caption_words":     r.get("caption_words", 100),
        "hashtag_count":     r.get("hashtag_count", 18),
        "timing_deviation":  abs(r.get("timing_deviation_hours", 0) or 0),
        # Targets
        "engagement_rate":   r.get("engagement_rate", 0),
        "save_rate":         r.get("save_rate", 0),
    }

STORY_TYPE_MAP = {
    "tip_repurpose":0,"poll":1,"behind_scenes":2,
    "reel_teaser":3,"weekly_roundup":4
}

def encode_story_record(r):
    return {
        "story_type_enc":  STORY_TYPE_MAP.get(r.get("story_type","tip_repurpose"), 0),
        "publish_hour":    r.get("publish_hour", 18),
        "slide_count":     r.get("slide_count", 1),
        # Targets
        "completion_rate":  r.get("completion_rate", 0),
        "interaction_rate": r.get("interaction_rate", 0),
    }

# ═══════════════════════════════════════════════════════════════════════
# Model phases
# ═══════════════════════════════════════════════════════════════════════

def get_model_phase(n_records):
    if n_records < 20:   return "bootstrap"
    if n_records < 50:   return "ridge"
    if n_records < 100:  return "bayesian"
    return "xgboost"

def run_bootstrap(records, target):
    """No model — return simple averages and hand-crafted insights."""
    if not records:
        return {
            "phase":   "bootstrap",
            "message": "Not enough data yet. Need 20+ posts.",
            "average": 0,
            "insights": []
        }
    values  = [r.get(target, 0) for r in records]
    average = round(np.mean(values), 4)
    best_type = max(
        set(r.get("content_type","static") for r in records),
        key=lambda t: np.mean([r.get(target,0) for r in records
                               if r.get("content_type")==t] or [0])
    )
    return {
        "phase":    "bootstrap",
        "average":  average,
        "best_content_type": best_type,
        "insights": [
            f"Average {target}: {average:.2%}",
            f"Best performing type so far: {best_type}",
            f"Based on {len(records)} posts — need 20 for model training"
        ]
    }

def run_ridge(encoded, target):
    """Ridge regression — interpretable linear model."""
    try:
        from sklearn.linear_model import RidgeCV
        from sklearn.preprocessing import StandardScaler

        feature_keys = [k for k in encoded[0] if k != target
                        and not k.endswith("_rate")
                        and k != "engagement_rate"
                        and k != "completion_rate"
                        and k != "interaction_rate"
                        and k != "save_rate"]

        X = np.array([[r[k] for k in feature_keys] for r in encoded])
        y = np.array([r.get(target, 0) for r in encoded])

        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X)

        model  = RidgeCV(alphas=[0.1, 1.0, 10.0])
        model.fit(X_sc, y)

        mae    = float(np.mean(np.abs(model.predict(X_sc) - y)))
        coeffs = dict(zip(feature_keys, model.coef_))

        # Rank features by absolute coefficient
        ranked = sorted(coeffs.items(), key=lambda x: abs(x[1]), reverse=True)

        insights = []
        for feat, coef in ranked[:5]:
            direction = "increases" if coef > 0 else "decreases"
            insights.append(f"{feat} {direction} {target} (coef: {coef:.4f})")

        return {
            "phase":        "ridge",
            "mae":          round(mae, 6),
            "top_features": ranked[:5],
            "insights":     insights,
            "coefficients": coeffs
        }
    except ImportError:
        return {"phase": "ridge", "error": "scikit-learn not installed"}
    except Exception as e:
        return {"phase": "ridge", "error": str(e)}

def run_bayesian(encoded, target):
    """Bayesian Ridge — handles sparse data better than plain Ridge."""
    try:
        from sklearn.linear_model import BayesianRidge
        from sklearn.preprocessing import StandardScaler

        feature_keys = [k for k in encoded[0] if k != target
                        and not k.endswith("_rate")
                        and k != "engagement_rate"
                        and k != "completion_rate"
                        and k != "interaction_rate"
                        and k != "save_rate"]

        X = np.array([[r[k] for k in feature_keys] for r in encoded])
        y = np.array([r.get(target, 0) for r in encoded])

        scaler = StandardScaler()
        X_sc   = scaler.fit_transform(X)

        model  = BayesianRidge()
        model.fit(X_sc, y)

        y_pred = model.predict(X_sc)
        mae    = float(np.mean(np.abs(y_pred - y)))

        coeffs  = dict(zip(feature_keys, model.coef_))
        ranked  = sorted(coeffs.items(), key=lambda x: abs(x[1]), reverse=True)

        insights = []
        for feat, coef in ranked[:5]:
            direction = "increases" if coef > 0 else "decreases"
            insights.append(f"{feat} {direction} {target} (coef: {coef:.4f})")

        return {
            "phase":        "bayesian",
            "mae":          round(mae, 6),
            "top_features": ranked[:5],
            "insights":     insights,
            "coefficients": coeffs,
            "alpha":        float(model.alpha_),
            "lambda":       float(model.lambda_)
        }
    except ImportError:
        return {"phase": "bayesian", "error": "scikit-learn not installed"}
    except Exception as e:
        return {"phase": "bayesian", "error": str(e)}

def run_xgboost(encoded, target):
    """XGBoost — captures compound effects. Feed model only at 100+ posts."""
    try:
        import xgboost as xgb
        from sklearn.model_selection import cross_val_score

        feature_keys = [k for k in encoded[0] if k != target
                        and not k.endswith("_rate")
                        and k != "engagement_rate"
                        and k != "completion_rate"
                        and k != "interaction_rate"
                        and k != "save_rate"]

        X = np.array([[r[k] for k in feature_keys] for r in encoded])
        y = np.array([r.get(target, 0) for r in encoded])

        model = xgb.XGBRegressor(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
            verbosity=0
        )
        model.fit(X, y)

        y_pred    = model.predict(X)
        mae       = float(np.mean(np.abs(y_pred - y)))
        importances = dict(zip(feature_keys, model.feature_importances_))
        ranked    = sorted(importances.items(), key=lambda x: x[1], reverse=True)

        insights = [f"{feat}: importance {imp:.4f}"
                    for feat, imp in ranked[:5]]

        return {
            "phase":            "xgboost",
            "mae":              round(mae, 6),
            "feature_importance": ranked[:5],
            "insights":         insights
        }
    except ImportError:
        return {"phase": "xgboost", "error": "xgboost not installed"}
    except Exception as e:
        return {"phase": "xgboost", "error": str(e)}

# ═══════════════════════════════════════════════════════════════════════
# Per-format breakdown
# ═══════════════════════════════════════════════════════════════════════

def compute_format_stats(records):
    """Compute average metrics per content type."""
    formats = {}
    for r in records:
        ct = r.get("content_type", "static")
        if ct not in formats:
            formats[ct] = []
        formats[ct].append(r)

    stats = {}
    for ct, recs in formats.items():
        eng  = [r.get("engagement_rate", 0) for r in recs]
        save = [r.get("save_rate", 0) for r in recs]
        stats[ct] = {
            "count":               len(recs),
            "avg_engagement_rate": round(np.mean(eng), 4),
            "avg_save_rate":       round(np.mean(save), 4),
            "best_engagement":     round(max(eng), 4),
        }
    return stats

def compute_timing_stats(records):
    """Find best posting day and hour."""
    by_day  = {}
    by_hour = {}
    for r in records:
        day  = r.get("publish_day", "monday")
        hour = r.get("publish_hour", 13)
        eng  = r.get("engagement_rate", 0)
        by_day.setdefault(day, []).append(eng)
        by_hour.setdefault(hour, []).append(eng)

    best_day  = max(by_day,  key=lambda d: np.mean(by_day[d]),  default="thursday")
    best_hour = max(by_hour, key=lambda h: np.mean(by_hour[h]), default=13)

    return {
        "best_day":        best_day,
        "best_hour_utc":   best_hour,
        "by_day":  {d: round(np.mean(v), 4) for d, v in by_day.items()},
        "by_hour": {str(h): round(np.mean(v), 4) for h, v in by_hour.items()},
    }

def compute_story_type_stats(records):
    """Compute average metrics per story type."""
    by_type = {}
    for r in records:
        st = r.get("story_type", "tip_repurpose")
        by_type.setdefault(st, []).append(r)

    stats = {}
    for st, recs in by_type.items():
        comp = [r.get("completion_rate", 0) for r in recs]
        intr = [r.get("interaction_rate", 0) for r in recs]
        stats[st] = {
            "count":                   len(recs),
            "avg_completion_rate":     round(np.mean(comp), 4),
            "avg_interaction_rate":    round(np.mean(intr), 4),
        }
    return stats

# ═══════════════════════════════════════════════════════════════════════
# Main analysis
# ═══════════════════════════════════════════════════════════════════════

def analyse_performance():
    print("=" * 50)
    print("Analysing performance")
    print("=" * 50)

    feed_records  = load_json("data/model/training.json", [])
    story_records = load_json("data/model/story_training.json", [])

    print(f"\nFeed training records:  {len(feed_records)}")
    print(f"Story training records: {len(story_records)}")

    results = {
        "analysed_at":      datetime.now().isoformat(),
        "feed_record_count":  len(feed_records),
        "story_record_count": len(story_records),
    }

    # ── Feed model ────────────────────────────────────────────────────
    print("\n── Feed model ──────────────────────────────")
    feed_phase = get_model_phase(len(feed_records))
    print(f"Phase: {feed_phase}")

    if feed_records:
        encoded_feed = [encode_feed_record(r) for r in feed_records]
        format_stats = compute_format_stats(feed_records)
        timing_stats = compute_timing_stats(feed_records)

        print(f"\nFormat stats:")
        for fmt, s in format_stats.items():
            print(f"  {fmt}: eng={s['avg_engagement_rate']:.2%} "
                  f"save={s['avg_save_rate']:.2%} (n={s['count']})")

        print(f"\nBest timing: {timing_stats['best_day']} "
              f"at {timing_stats['best_hour_utc']}:00 UTC")

        if feed_phase == "bootstrap":
            feed_model = run_bootstrap(feed_records, "engagement_rate")
        elif feed_phase == "ridge":
            feed_model = run_ridge(encoded_feed, "engagement_rate")
            print(f"Ridge MAE: {feed_model.get('mae',0):.6f}")
        elif feed_phase == "bayesian":
            feed_model = run_bayesian(encoded_feed, "engagement_rate")
            print(f"Bayesian MAE: {feed_model.get('mae',0):.6f}")
        else:
            feed_model = run_xgboost(encoded_feed, "engagement_rate")
            print(f"XGBoost MAE: {feed_model.get('mae',0):.6f}")

        for insight in feed_model.get("insights", []):
            print(f"  → {insight}")

        results["feed_model"]    = feed_model
        results["format_stats"]  = format_stats
        results["timing_stats"]  = timing_stats
    else:
        print("No feed data yet — skipping feed model")
        results["feed_model"] = {"phase": "bootstrap",
                                  "message": "No data yet"}

    # ── Story model ───────────────────────────────────────────────────
    print("\n── Story model ─────────────────────────────")
    story_phase = get_model_phase(len(story_records))
    print(f"Phase: {story_phase}")

    if story_records:
        encoded_stories = [encode_story_record(r) for r in story_records]
        story_stats     = compute_story_type_stats(story_records)

        print(f"\nStory type stats:")
        for st, s in story_stats.items():
            print(f"  {st}: completion={s['avg_completion_rate']:.2%} "
                  f"interaction={s['avg_interaction_rate']:.2%} "
                  f"(n={s['count']})")

        if story_phase == "bootstrap":
            story_model = run_bootstrap(story_records, "interaction_rate")
        elif story_phase in ("ridge", "bayesian"):
            story_model = run_bayesian(encoded_stories, "interaction_rate")
            print(f"Bayesian MAE: {story_model.get('mae',0):.6f}")
        else:
            # Story model stays Bayesian even at 100+ records
            story_model = run_bayesian(encoded_stories, "interaction_rate")
            print(f"Bayesian MAE: {story_model.get('mae',0):.6f}")

        for insight in story_model.get("insights", []):
            print(f"  → {insight}")

        results["story_model"] = story_model
        results["story_stats"] = story_stats
    else:
        print("No story data yet — skipping story model")
        results["story_model"] = {"phase": "bootstrap",
                                   "message": "No data yet"}

    # Save results
    out_path = "data/model/analysis_results.json"
    save_json(out_path, results)
    print(f"\nAnalysis saved to {out_path}")
    print("=" * 50)

    return results

if __name__ == "__main__":
    analyse_performance()