"""Kuku Promo Finder - web app.   Run:  streamlit run app.py

Drop in screenplay .txt files (or a .zip) - or point at a folder - and get ranked promo
clips: episode, every segment's start/end, hook, cliffhanger, why. Nothing is uploaded
anywhere except to the LLM provider you explicitly choose in the sidebar.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from promo_finder.envfile import load_dotenv
from promo_finder.evaluate import cliffhanger_note_eval, hard_checks
from promo_finder.llm import LLMError, make_client
from promo_finder.parse import load_inputs, load_uploaded
from promo_finder.pipeline import RunConfig, run
from promo_finder.report import CSV_COLUMNS, _csv_row, markdown

st.set_page_config(page_title="Kuku Promo Finder", page_icon="🎬", layout="wide")
load_dotenv()  # optional .env with LLM_* keys (never printed)


def default_folder() -> str:
    for cand in ("data/raw", "sample_data"):
        p = Path(cand)
        if p.is_dir() and any(p.rglob("*.txt")):
            return cand
    return ""


@st.cache_data(show_spinner=False)
def compute_heuristic(source: str, uploads: tuple, per_episode: int, recommended: int):
    """Free, offline path - cached so moving a slider never re-parses."""
    if uploads:
        episodes, report = load_uploaded(list(uploads))
    else:
        episodes, report = load_inputs(source)
    cfg = RunConfig(per_episode=per_episode, recommended_top=recommended)
    res = run(episodes, cfg)
    return {"episodes": episodes, "report": report, "result": res,
            "checks": hard_checks(res.promos, episodes, cfg.min_s, cfg.max_s, cfg.max_overlap),
            "notes_eval": cliffhanger_note_eval(res.promos, episodes)}


def compute_llm(source, uploads, per_episode, recommended, opts, progress):
    episodes, report = load_uploaded(list(uploads)) if uploads else load_inputs(source)
    cfg = RunConfig(per_episode=per_episode, recommended_top=recommended, judge="llm",
                    llm_topk=opts["topk"], llm_weight=opts["weight"], max_llm_calls=opts["max_calls"])
    client = make_client(opts["provider"], opts["model"], api_key=opts["key"] or None,
                         base_url=opts["base"] or None, cache_dir=".llm_cache", max_calls=opts["max_calls"])
    res = run(episodes, cfg, llm_client=client, progress=progress)
    return {"episodes": episodes, "report": report, "result": res,
            "checks": hard_checks(res.promos, episodes, cfg.min_s, cfg.max_s, cfg.max_overlap),
            "notes_eval": cliffhanger_note_eval(res.promos, episodes)}


# ------------------------------------------------------------------ sidebar
st.title("🎬 Kuku Promo Finder")
st.caption("Finds 20-60 s promo clips in microdrama screenplays: a hook in the first 3 s, a cliffhanger ending, "
           "and a scene that makes sense on its own.")

with st.sidebar:
    st.header("1 · Input")
    mode = st.radio("Where are the screenplays?", ["Folder on this machine", "Upload files"],
                    index=0 if default_folder() else 1)
    folder, uploads = "", ()
    if mode == "Folder on this machine":
        folder = st.text_input("Folder, .txt or .zip path", value=default_folder(),
                               help="Default: data/raw if present, otherwise the bundled sample_data.")
    else:
        files = st.file_uploader("Screenplay .txt files or one .zip", type=["txt", "zip"],
                                 accept_multiple_files=True)
        uploads = tuple((f.name, f.getvalue()) for f in files or [])

    st.header("2 · Settings")
    per_episode = st.slider("Promos kept per episode", 1, 5, 3)
    recommended = st.slider("Mark top N as 'post first'", 3, 50, 15)

    st.header("3 · Judge")
    judge = st.radio("Judge", ["Heuristic (free, offline)", "LLM re-ranking (needs an API key)"], index=0,
                     help="The LLM only sees a shortlist of windows chosen by the heuristic pass.")
    llm_opts = {}
    if judge.startswith("LLM"):
        llm_opts["provider"] = st.selectbox("Provider", ["anthropic", "openai"],
                                            help="'openai' = any OpenAI-compatible endpoint (OpenAI, Gemini, Groq, Ollama...)")
        llm_opts["model"] = st.text_input("Model name", help="Check your provider's current model list.")
        llm_opts["base"] = st.text_input("Base URL (optional)", placeholder="https://.../v1")
        llm_opts["key"] = st.text_input("API key", type="password", help="Kept in this browser session only.")
        llm_opts["topk"] = st.slider("Windows per episode sent to the LLM", 2, 10, 6)
        llm_opts["weight"] = st.slider("LLM weight in final score", 0.0, 1.0, 0.6, 0.05)
        llm_opts["max_calls"] = st.number_input("Max paid calls (budget guard)", 1, 5000, 300)
        st.caption("Rough cost: calls ≈ episodes × windows per episode; ~1k input tokens each.")
    go = st.button("▶ Run", type="primary", width="stretch")

# ------------------------------------------------------------------ run
if not folder and not uploads:
    st.info("Choose a folder or upload screenplay files in the sidebar to begin. "
            "No screenplays handy? Use the bundled `sample_data` folder.")
    st.stop()

state = st.session_state
is_llm = judge.startswith("LLM")
# results are only shown for the settings that produced them (never stale or from another judge)
signature = (is_llm, folder, tuple((n, len(b)) for n, b in uploads), per_episode, recommended,
             tuple(sorted((k, str(v)) for k, v in llm_opts.items() if k != "key")))
try:
    if is_llm:
        if go:
            if not llm_opts.get("model"):
                st.error("Enter a model name for the LLM judge.")
                st.stop()
            bar = st.progress(0.0, text="Starting…")
            state["data"] = compute_llm(folder, uploads, per_episode, recommended, llm_opts,
                                        lambda i, n, m: bar.progress(min(i / max(n, 1), 1.0), text=m))
            state["signature"] = signature
            bar.empty()
        elif state.get("signature") != signature or "data" not in state:
            st.info("Set the LLM options and press **Run**. (Nothing is sent to a provider until you do.)")
            st.stop()
    else:
        with st.spinner("Scoring every clean-cut window…"):
            state["data"] = compute_heuristic(folder, uploads, per_episode, recommended)
        state["signature"] = signature
except FileNotFoundError as exc:
    st.error(f"Input not found: {exc}")
    st.stop()
except LLMError as exc:
    st.error(f"LLM problem: {exc}")
    st.stop()
except Exception as exc:  # keep the UI alive and explain
    st.error(f"Something went wrong while processing: {type(exc).__name__}: {exc}")
    st.stop()

data = state["data"]
res, episodes = data["result"], data["episodes"]
bad_files = [r for r in data["report"] if r["status"] in ("error", "skipped")]
if not res.promos:
    st.warning("No promo windows were found. The episodes may be shorter than 20 s or have too little dialogue.")
    st.stop()

passed = all(c["passed"] for c in data["checks"])
c1, c2, c3, c4 = st.columns(4)
c1.metric("Episodes", res.n_episodes)
c2.metric("Windows scored", f"{res.n_candidates:,}")
c3.metric("Promos ranked", len(res.promos))
c4.metric("Hard checks", "all passed ✅" if passed else "FAILED ⚠️")
for r in bad_files:
    st.warning(f"Skipped {r['file']}: {r['warnings']}")
for n in res.notes:
    st.caption(f"ℹ️ {n}")

tab_rank, tab_view, tab_quality, tab_run = st.tabs(["🏆 Ranked promos", "🔍 Inspect a promo", "✅ Quality", "ℹ️ Run details"])

flat = pd.DataFrame([_csv_row(p) for p in res.promos], columns=CSV_COLUMNS)

with tab_rank:
    f1, f2, f3 = st.columns(3)
    eps = f1.multiselect("Episodes", sorted(flat["episode"].unique()))
    kinds = f2.multiselect("Type", sorted(flat["kind"].unique()))
    only_rec = f3.checkbox("Only 'post first'", value=False)
    view = flat
    if eps:
        view = view[view["episode"].isin(eps)]
    if kinds:
        view = view[view["kind"].isin(kinds)]
    if only_rec:
        view = view[view["recommended"] == "yes"]
    st.dataframe(view[["rank", "recommended", "episode", "kind", "segments", "duration", "score", "why", "flags"]],
                 hide_index=True, width="stretch")
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ CSV", flat.to_csv(index=False).encode("utf-8-sig"), "promos_ranked.csv", "text/csv")
    d2.download_button("⬇ JSON", json.dumps(res.promos, indent=2, ensure_ascii=False).encode("utf-8"),
                       "promos_ranked.json", "application/json")
    d3.download_button("⬇ Markdown", markdown(res, recommended).encode("utf-8"), "promos_ranked.md", "text/markdown")

with tab_view:
    labels = {f"#{p['rank']} · EP{p['episode']:02d} · {p['start_ts']}–{p['end_ts']} · {p['score']:.0f} pts": p
              for p in res.promos}
    p = labels[st.selectbox("Promo", list(labels))]
    st.subheader(f"EP{p['episode']:02d} — " + "  +  ".join(f"{g['start_ts']}–{g['end_ts']}" for g in p["segments"])
                 + f"  ({p['duration']:.0f} s)")
    st.write(f"**Why it works:** {p['why']}")
    a, b = st.columns(2)
    a.success(f"**Hook (first {p['hook_at_s']:.1f} s)**\n\n{p['hook']}")
    b.warning(f"**Cliffhanger**\n\n{p['cliffhanger']}\n\n*Cut before:* {p['cut_before'] or '(episode ends)'}")
    if p["flags"]:
        st.error("Check before posting: " + "; ".join(p["flags"]))
    if p.get("llm"):
        st.info(f"LLM verdict: **{p['llm']['verdict']}** (overall {p['llm']['overall']:g}) — risk: {p['llm']['risk']}")
    st.bar_chart(pd.Series(p["parts"], name="points"))
    rows = []
    last = len(p["transcript"]) - 1
    hook_is_dialogue = not p["hook"].startswith("[ACTION]")
    for i, t in enumerate(p["transcript"]):
        role = "🎣 hook" if (i == 0 and hook_is_dialogue) else ("🧗 cliffhanger" if i == last else "")
        rows.append({"t (s)": t["t"], "": role, "speaker": t["speaker"], "delivery": ", ".join(t["tags"][:2]),
                     "line": t["text"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Timestamps are screenplay times. There is no video in the input: an editor must watch the cut.")

with tab_quality:
    st.markdown("**Structural checks** (every promo; these validate data integrity, not editorial quality)")
    st.dataframe(pd.DataFrame(data["checks"])[["check", "passed", "failures"]], hide_index=True, width="stretch")

    st.markdown("### Editorial score reliability")
    st.info(
        "The heuristic score is a deterministic ranking aid, not a probability that a promo will perform well. "
        "A passed structural check does not mean the clip is editorially strong. Review candidates against the "
        "same rubric before changing weights or describing the score as validated."
    )
    st.caption(
        "Recommended human rubric: hook (0–5), context clarity (0–5), emotional impact (0–5), "
        "escalation (0–5), ending strength (0–5). Convert the weighted total to 0–100 only after review."
    )
    review = flat[["rank", "episode", "segments", "duration", "score", "why", "flags"]].copy()
    review["human_hook_0_5"] = ""
    review["human_context_0_5"] = ""
    review["human_emotion_0_5"] = ""
    review["human_escalation_0_5"] = ""
    review["human_ending_0_5"] = ""
    review["human_verdict_keep_reject"] = ""
    review["reviewer_notes"] = ""
    st.download_button(
        "⬇ Download human-review sheet",
        review.to_csv(index=False).encode("utf-8-sig"),
        "promo_human_review_template.csv",
        "text/csv",
        help="Fill in the five human ratings and verdict, then use the reviewed rows to evaluate ranking quality."
    )

    n = data["notes_eval"]
    if n.get("n"):
        st.markdown(f"**Agreement with the show's own cliffhanger notes** (n = {n['n']} episodes)")
        st.dataframe(pd.DataFrame([
            {"method": "this tool", "top-1": f"{n['v2_top1_hits']}/{n['n']}", "any of top-3": f"{n['v2_anyk_hits']}/{n['n']}"},
            {"method": "baseline: the episode's final window", "top-1": f"{n['last_window_hits']}/{n['n']}", "any of top-3": "-"},
            {"method": "baseline: random windows (expected)", "top-1": f"{n['random_expected_hits']}/{n['n']}", "any of top-3": "-"},
        ]), hide_index=True, width="stretch")
    else:
        st.caption("No cliffhanger notes in this input (or fewer than 3 usable key words), so that check was skipped.")

with tab_run:
    st.json({"judge": res.config.judge, "seconds": res.seconds, "llm_usage": res.llm_usage,
             "config": res.config.__dict__})
    st.dataframe(pd.DataFrame(data["report"]), hide_index=True, width="stretch")
