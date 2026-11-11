# Board-Room Debate

A Streamlit application for strategic decisions, with CEO, CFO, CMO, Risk Officer and Moderator agents, an optional Researcher, visible dissent, deterministic financial calculations, and three human review points. Built from the supplied BoardRoom build prompt v0.2 and workbook v0.3.

**Start with Demo Run.** It replays a fictional Indian consumer-electronics market-entry case without credentials or internet after installation. Live responses require your own provider access.

## Use your ChatGPT subscription

Your requested subscription option uses **your own ChatGPT account instead of Claude subscription access**. There are two ways to use it:

| Mode | On Streamlit Community Cloud | On your laptop | What you supply |
|---|---|---|---|
| Offline demo | Yes | Yes | Nothing; canned sample responses |
| ChatGPT subscription — copy and paste | Yes | Yes | Copy each prompt into ChatGPT; paste JSON back |
| ChatGPT subscription — automatic Codex CLI | No, disabled in hosted mode | Yes | Recent Codex CLI signed in with your own eligible ChatGPT plan |
| OpenAI API — automatic | Yes | Yes | Your own OpenAI API key and API account access |
| Anthropic API — automatic | Yes | Yes | Your own Anthropic API key and API account access |

**A hosted Streamlit server cannot access the Codex installation or ChatGPT login on your laptop.** ChatGPT subscription access is not an API key. Automatic hosted runs use separately metered API access (or eligible API credits, if your account has them). This project does not scrape ChatGPT, copy session cookies, accept passwords, or upload your Codex login file to a server. Never put `auth.json` in GitHub or Streamlit Secrets. Each user must use their own account and check current provider terms and plan limits.

### ChatGPT subscription on your hosted app

1. Select **ChatGPT subscription → Copy and paste with ChatGPT**.
2. Enter the decision brief and start the debate.
3. Open each **ChatGPT handoff**, copy its complete prompt, and paste it into a separate ChatGPT conversation for that task.
4. Ask ChatGPT to return only the JSON object. Paste it into the corresponding response box and submit.
5. Complete the human reviews as they appear. The app validates the JSON, shows the workflow and compiles the memo.

This is a human-mediated workflow, not an automatic connection to your ChatGPT account. A run with four functional agents, Researcher and two rounds needs 11 handoffs (plus any malformed-output retries). You can disable Researcher or select one round to shorten it. No API charge is incurred by this app in this mode; your ChatGPT plan usage limits still apply.

## Upload to GitHub and host on Streamlit

1. Extract the ZIP.
2. Create a GitHub repository, for example `boardroom-debate`.
3. Upload the **contents of the extracted `boardroom-debate` folder**, preserving its subfolders. `app.py` and `requirements.txt` should be at the repository root. Do not upload the ZIP itself as the app.
4. In [Streamlit Community Cloud](https://share.streamlit.io/), choose **Create app**, connect the repository, choose your branch (usually `main`), and set **Main file path** to `app.py`.
5. Under **Advanced settings**, choose Python **3.11** (3.12 also tested). No API key or login secret is required to deploy.
6. Deploy, open the app, and press **Demo Run** to verify installation.
7. For your own case, use ChatGPT copy/paste handoffs or enter your own API key in the sidebar.

If you uploaded the parent directory instead, set Main file path to `boardroom-debate/app.py`; keeping `app.py` at the root is simpler. Make sure `requirements.txt` and the `boardroom/` Python package remain beside it. GitHub's browser uploader can omit hidden files: upload `.streamlit/config.toml` separately if necessary so the theme and telemetry setting are retained. No `packages.txt`, database, GPU, JavaScript build step or shared key is needed.

The app does not provide an employee login system. Use hosting access controls/private deployment when company information requires restricted access. In hosted mode the host necessarily receives your inputs; extracted evidence is then sent only to the selected LLM provider by the app. In manual mode, you decide when to copy it to ChatGPT.

## Run on Windows or Mac with one command

Prerequisite: Python 3.11 or newer. In the extracted project directory:

```bash
python launch.py
```

On a Mac where the executable is named `python3`, use `python3 launch.py`. The launcher creates `.venv`, installs dependencies on first run, and starts the local app bound to `127.0.0.1`. First installation needs internet; the installed demo does not. Dependency-install failure is shown in the terminal. Open the displayed local URL. No GPU is required.

Manual alternative:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

For local Codex integration, use the launcher, or set `BOARDROOM_LOCAL=1` yourself before running Streamlit. Do not enable this setting on a multi-user public server.

### Automatic use of your local ChatGPT subscription

1. Install a current [Codex CLI](https://learn.chatgpt.com/docs/cli) using the official instructions. The adapter requires `codex exec --ephemeral`, `--ignore-user-config` and `--output-schema`. If your CLI does not support these flags, update it.
2. Sign in with your **own ChatGPT account** using a separate, clean Codex home. This keeps your normal Codex plugins, MCP tools and project settings out of board debates.

Mac/Linux:

```bash
CODEX_HOME="$HOME/.boardroom-codex" codex login
```

Windows PowerShell:

```powershell
$env:CODEX_HOME = "$env:USERPROFILE\.boardroom-codex"
codex login
```

3. Complete ChatGPT login in your browser. Do not select API-key login for this mode.
4. Start `python launch.py`. Select **ChatGPT subscription → Local Codex CLI**. Leave the model blank to use the CLI account default, or enter a model your plan supports.
5. Start the debate. The app checks login, invokes Codex locally and validates its structured output. If Codex is missing, not signed in, rate limited or incompatible, it reports the error without falling back to paid API usage.

The dedicated Codex home is outside this repository. Do not add MCP servers, plugins, hooks or custom model providers there. The adapter runs from a temporary empty directory with ephemeral sessions, read-only sandbox, shell tools disabled, web search disabled, and the OpenAI provider selected. Temporary schema and final-response files are deleted after each call. Authentication stays under Codex control; the app does not read, copy or export access tokens. Codex itself may maintain authentication and diagnostic data according to its own settings and policies. Review provider terms and usage limits before use.

## Run a debate

1. Choose provider/model and supply your own API key, if using an API. The sidebar includes custom model IDs because provider access changes over time.
2. Enter the question, options, company, sector, budget, context, horizon and risk appetite. Choose active roles and 1–3 **total** rounds. Moderator is always present; Researcher is optional.
3. Enter financial assumptions in **INR lakh**. Upload up to five PDF/TXT/XLSX files of up to 10 MB each. Text extraction happens on the app server, without executing document instructions or spreadsheet formulas.
4. Confirm the selected-provider data use and start.
5. **Review 1:** confirm or edit the Moderator's framed question and options before other agents run.
6. **Review 2:** after each debate round, inject a challenge, change financial assumptions, continue, or end early. If the round cap is reached, the Moderator addresses new feedback in the final synthesis; no unbudgeted extra round is added.
7. **Review 3:** accept, edit/override or reject the recommendation. Record the board's decision and optional edited summary/note. This remains separate from the original AI recommendation in the audit trail.
8. Download the concise DOCX/PDF memo and full JSON transcript. A Markdown memo is also available.

The board decides; the app advises. Scores and confidence are subjective judgments, not calibrated probabilities. Similar stances do not establish that evidence is correct.

## Controls and traceability

- **Canvas:** every role has an idle/thinking/done/failed state, brief current input/output, and animated active transfer arrows. Disabled roles show `off`. Inspect a role for its full structured output and latest input snapshot. The final memo box is the Moderator's synthesis stage.
- **Transcript:** role-tagged structured messages, with source labels on claims. JSON includes source registry, input versions, human reviews, calculator snapshots, retries, state transitions and scorecard.
- **Parallelism:** LangGraph executes active functional agents concurrently against the same completed prior-round snapshot. No agent sees another opening position before producing its own. Research and framing run before the opening. Moderator synthesises the completed debate.
- **Pause/Step:** these operate at stage boundaries. A stage is framing, research, one parallel functional round, or synthesis. Pause lets an in-flight stage finish. Step permits one additional stage, then pauses. Human checkpoints still require explicit input.
- **Stop:** prevents further stages and discards responses that arrive after stopping. It terminates a local CLI process. Already submitted API requests may continue at the provider and may be billed.
- **Round cap:** 1–3 rounds including the opening. Review can end the debate early. We do not infer numerical convergence from a small simulated panel; the user controls early termination.
- **Cost cap:** API calls reserve a conservative input/output estimate atomically before launch, including concurrent calls and retries. SDK retries are disabled. Actual reported token usage replaces reservations when available; failed requests conservatively retain the reserved estimate. Enter current USD rates for the model. This is an application estimate, excludes tax and unrelated account usage, and is not a provider-enforced billing limit. Cached-token discounts are not assumed. Subscription/manual/demo usage is not priced as API tokens.
- **Reliability:** every agent output is validated by Pydantic against a structured schema, role/phase, source registry, three functional arguments, rebuttal word limit and five final risks. Malformed output receives up to two repair attempts. Friendly provider failures appear in the failing box; raw SDK exception bodies and credentials are not logged.

## Evidence and calculator assumptions

All narrative claims carry one allowed source ID or `assumption`. Supported sources include `brief`, `confirmed_frame`, `file:1:p1` (PDF page), `file:1:sheet1` (workbook sheet), `file:1:text`, `calc:base`, `calc:downside`, and human challenge IDs. Labels prove only where a statement came from, not whether it is supported correctly. The schema rejects invented source IDs; it cannot verify semantic truth. Review cited excerpts before acting.

Financial calculations:

- Initial investment occurs at time zero; annual cash flows occur at year-end.
- Annual cash flow = revenue × contribution margin − annual fixed operating costs.
- NPV = negative initial investment + discounted annual cash flows.
- Payback is undiscounted, interpolated within the first year cumulative cash flow becomes nonnegative. `Not reached` means the forecast horizon ends before recovery; later negative flows can reverse recovery.
- Operating break-even annual revenue = annual fixed costs / contribution margin. This excludes recovery of capex. Zero margin makes the ratio undefined.
- Downside holds costs, margin and capex constant and reduces each year's revenue by 25%.
- No tax, depreciation tax shield, working capital, terminal value, financing or inflation adjustment. These are simplified teaching calculations, not a complete investment model. The supplied contribution margin must exclude the fixed costs entered separately.
- Human revisions update the calculator and preserve earlier input/calculation versions in the transcript. `calc:base` in a historical message refers to that message's input snapshot; the top-level calculator is the latest version.

File limits: unencrypted, text-based PDFs up to 200 pages; UTF-8 TXT; XLSX up to 20 sheets, 5,000 rows per sheet and 40 columns. Spreadsheet formula cached values are used, never recalculated; recalculate and save in Excel before upload. Scanned PDFs need OCR first. A file's extracted text is limited to 70,000 characters and combined evidence to 100,000. Larger files are rejected rather than silently summarised. No vector store or external document service is used.

## Scope choices and adaptations

These implement or clarify ambiguities in the supplied prompt/workbook:

1. **LangGraph** was selected over CrewAI for explicit parallel graph nodes and predictable typed state. A session controller manages human checkpoints and pause/step between graph stages. No hosted LangSmith service is required.
2. Your subscription preference replaces the Claude subscription adapter with **ChatGPT via local Codex CLI**. A **manual ChatGPT handoff** is added to make your subscription usable with the hosted app without uploading account tokens.
3. **Researcher uses supplied sources only.** Optional web search, Yahoo Finance, Screener, Drive/SharePoint, vector stores and additional use cases are not implemented. Web search is off with no hidden outbound retrieval.
4. **Round count means total rounds**, including one opening round; later rounds are rebuttals. Checkpoint 2 repeats after each round. There is no extra challenge round beyond the cap.
5. Final human editing covers the board recommendation, summary and note. It records an override without silently rewriting the agent transcript. Further memo editing is available in the downloaded DOCX.
6. The offline demo always loads the shipped fictional sample case and canned positions. It records human feedback but does not generate new reasoning or bespoke answers to challenges.
7. DOCX and PDF exports aim for a two-page brief for normal concise outputs. Long claims are shortened in those briefs; full content remains in JSON and Markdown. Extreme/custom model responses may produce more pages. PDF uses standard Latin fonts; choose DOCX for Bengali or other Indian scripts.
8. No automatic persistent history or authentication server is added. Each browser session has its own in-memory state/provider. Closing/clearing a session or restarting the host loses that run unless exported. Idle workers cancel after 15 minutes without UI polling; manual handoffs expire after 30 minutes. Do not use this prototype as an unattended service.

## Credentials and data handling

The app never ships a real key, login, company document or shared subscription. API credentials are held in that visitor's session/worker memory and sent only to the fixed selected provider endpoint. They are excluded from graph state, memo and transcript exports. SDK clients close after calls; the worker's key reference is cleared when a run finishes. The password field may retain your key in Streamlit session state until you clear the session or disconnect. **Clear session** releases those values; Python cannot guarantee secure zeroing of memory.

For optional local use, copy `.env.example` to `.env` and set your own API key. `.env` is ignored by Git and loaded only in local mode. Do not put keys in `data/sample_case.json`, source files, GitHub, workflow files or public Streamlit Secrets. Avoid pasting credentials into the decision brief or company evidence, since those inputs are sent to the provider and exported as part of the transcript.

The app writes no application transcript logs to disk, adds no telemetry and disables LangSmith/LangChain tracing. Streamlit usage collection is disabled in `.streamlit/config.toml`. Hosting and provider services still apply their own retention and access policies. Downloaded transcripts include evidence text and can be sensitive. This is a prototype; use appropriate hosting access controls for internal material.

## Files

```text
app.py                         Streamlit UI and session controls
launch.py                      One-command local setup and launch
requirements.txt               Runtime dependencies
requirements-dev.txt           Test dependencies
requirements-tested.txt        Exact direct versions used in verification
boardroom/models.py            Structured outputs and validation
boardroom/engine.py            Session controller and parallel LangGraph stages
boardroom/providers.py         Demo, OpenAI, Anthropic, ChatGPT handoff / Codex
boardroom/prompts.py            Role instructions and evidence handling
boardroom/demo.py               Fixed offline responses
boardroom/finance.py            Deterministic finance calculations
boardroom/inputs.py             PDF/TXT/XLSX extraction
boardroom/exports.py            Markdown, DOCX and PDF exports
boardroom/canvas.py             Live workflow SVG
data/sample_case.json           Fictional FY27 market-entry case
tests/                         Offline engine, parsing, calculator and UI tests
.streamlit/config.toml         Theme and telemetry setting
.github/workflows/tests.yml     GitHub Actions on Python 3.11 and 3.12
.env.example                   Empty local credential template
.gitignore                     Excludes local credentials and environments
```

## Tests

From the project root:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover financial edge cases, offline end-to-end debate, all human checkpoints, rounds/disabled roles, same-snapshot parallel inputs, pause/step/stop, malformed-output repair, source rejection, manual ChatGPT handoffs, key exclusion, atomic cost reservations, file parsing and the Streamlit UI. No paid provider calls are made by tests. GitHub Actions repeats tests on Python 3.11 and 3.12 after you upload the repo. Local verification was performed on Python 3.12; live API and your personal Codex login require your account and are not claimed as tested here.

## Troubleshooting

| Problem | Action |
|---|---|
| `ModuleNotFoundError` on Streamlit Cloud | Ensure root `requirements.txt` and `boardroom/` were uploaded; reboot/redeploy |
| ChatGPT subscription asks for responses | This is the cloud-compatible manual mode; use API mode for automatic cloud calls or local Codex for your subscription |
| Codex option not visible | Start locally with `python launch.py`; the hosted app deliberately hides local account access |
| Codex missing/not logged in | Update/install CLI and log in with the dedicated CODEX_HOME described above |
| Codex fails despite login | Verify supported CLI flags, model access and plan limits; the app never falls back to an API key |
| API authentication/quota error | Check your own key, account billing and selected model permissions |
| Cost cap reached before first request | Increase cap or reduce input size; verify the editable model rates |
| Invalid structured output three times | Check model structured-output support; in manual mode return the full JSON schema with valid source IDs |
| PDF upload contains no text | OCR the scanned PDF first |
| Spreadsheet has blank formula cells | Recalculate and save in Excel; only cached values are read |
| Round finished but nothing happens | Complete the human review or press Resume/Step if paused |
| Memo is marked draft | Complete final board review; the exported audit trail records the disposition |
| App restarted or session expired | Start a new run; download JSON before closing if you need to keep it |

## Official references

- [Codex authentication and ChatGPT login](https://learn.chatgpt.com/docs/auth)
- [Codex non-interactive execution and structured output](https://learn.chatgpt.com/docs/non-interactive-mode)
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages)
- [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)

Checked while preparing this package on 11 November 2026. Provider terms, model availability, plans and prices can change.
