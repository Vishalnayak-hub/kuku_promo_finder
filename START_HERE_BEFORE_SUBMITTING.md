# Start here - what is ready, and the 6 things only you can do

## What is already done (in this zip)
* `submission/Kuku_Promo_Finder_Solution.pdf` - the 2-page solution doc (also in `docs/`).
* `submission/raw_outputs/` - unedited outputs of **one** CLI run on the full 50-episode pack.
* The prototype: `promo_finder/` + `app.py`, 42 passing tests, sample show, README, execution guide.

## Your checklist (about 60-90 minutes)

1. **Read it so you can explain it** (30 min - the interview will ask). Start with `README.md`, then `docs/CHANGES_FROM_V1.md`,
   then skim `promo_finder/scoring.py` (the 5 sub-scores) and `promo_finder/llm.py` (what the LLM may and may not do).
   Open `submission/raw_outputs/promos_ranked.md` and watch/read 3 promos yourself. Edit `docs/REVIEW_NOTES.md` with your own verdicts.
   **The PDF says Claude wrote the v2 rebuild and ChatGPT built v1. Keep that true - if you used other tools, change section 7 in
   `docs/build_solution_pdf.py` and rebuild.**
2. **Push the code to GitHub** (the repo already exists; the old files are replaced):
   ```bash
   git add -A
   git status        # CHECK: no data/ , no outputs/ , no submission/raw_outputs/ , no .env in the list
   git commit -m "v2: rebuilt promo finder - all episodes, LLM judge, tests, app"
   git push
   ```
3. **Deploy the app (free):** share.streamlit.io -> New app -> your repo, branch `main`, file `app.py`,
   *Advanced settings -> Python 3.12*. It will start on the bundled `sample_data`; anyone can upload screenplays.
   Put the URL in the form. (Do NOT upload Kuku's pack to a public app.)
4. **Run the LLM judge once with a free-tier key** - this is the one thing I could not do (no API access when building):
   ```bash
   copy .env.example .env            # fill LLM_MODEL and LLM_API_KEY (macOS/Linux: cp)
   python -m promo_finder run --judge llm --dry-run
   python -m promo_finder run --judge llm --max-llm-calls 200 --out outputs_llm
   ```
   Compare `outputs_llm/promos_ranked.md` with `submission/raw_outputs/`. If it works, add one sentence with the real result to
   section 8 of `docs/build_solution_pdf.py`, then `python docs/build_solution_pdf.py` and copy the PDF to `submission/`.
   If it fails, the heuristic outputs still stand and the PDF already says the LLM path is untested live.
5. **Raw outputs link:** upload the folder `submission/raw_outputs/` to Google Drive -> Share -> *Anyone with the link*.
   (Outputs quote Kuku's screenplay lines - Drive link only, never a public GitHub repo.)
6. **Optional 3-minute video:** follow `docs/WALKTHROUGH_3MIN.md`. Then fill the form: name, roll number, branch, Problem 1,
   PDF, GitHub link, app link, Drive link, video link. Open each link in a private window to confirm it works.

## If you change anything
`pytest -q` must stay green. If you re-run the pipeline, rebuild the PDF (`python docs/build_solution_pdf.py`) so numbers match.
