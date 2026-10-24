# Satyapan — one-command workflows.
# Uses `uv` by default. Without uv, activate your venv and run e.g. `make check RUN=`
RUN ?= uv run
T ?=
# Satya's ears: mlx-whisper on Apple Silicon, faster-whisper everywhere else.
ifeq ($(shell uname -s)-$(shell uname -m),Darwin-arm64)
ASR_EXTRAS ?= --extra asr --extra asr-mac
else
ASR_EXTRAS ?= --extra asr
endif

.PHONY: scan help sync asr video voice video-models doctor demo-audio live live-personal check lint fmt typecheck test task run demo-data schemas status judge dry-run console-test ext-test clean

help:
	@echo "make sync          install core + dev deps (uv)"
	@echo "make check         lint + format check + typecheck + all tests (run before every commit)"
	@echo "make test          all tests (task tests skip until their task is implemented)"
	@echo "make task T=T07    run ONLY task T07's acceptance tests, strict (no skipping)"
	@echo "make run           start the API on http://127.0.0.1:8000 (docs at /docs)"
	@echo "make asr           install Satya's local speech engine + download the model (once)"
	@echo "make video         install the face check (video deepfakes) + verify its models"
	@echo "make voice         build + install the voice-clone model (needs torch once)"
	@echo "make demo-audio    generate the labelled DEMO REPLAY call (synthetic voice, once)"
	@echo "make doctor        check the speech engine is ready and fast enough on this laptop"
	@echo "make live          start the API for a live demo (no auto-reload, model warmed up)"
	@echo "make demo-data     regenerate data/demo fixtures + schemas and validate them"
	@echo "make status        print the task board from docs/STATUS.md"
	@echo "make judge         score the detector stack + check a judge's own input"
	@echo "make dry-run       automated end-to-end rehearsal (real app, fake speech)"

sync:
	uv sync --inexact

# Once per laptop, before the demo (needs internet the first time).
asr:
	uv sync --inexact $(ASR_EXTRAS)
	$(RUN) python scripts/asr_check.py

# The face check for video calls (docs/VIDEO_DEEPFAKE.md). Windows without make:
#   uv run python scripts/satya.py video
video:
	uv sync --inexact --extra video --extra ocr
	$(RUN) python scripts/video_models.py

# The voice-clone check (docs/VOICE_DEEPFAKE.md): builds model.onnx from the pinned XLS-R
# revision and logreg_prob.onnx from config/voice_head.json, checks them against PyTorch and
# installs both in extension/models/. Needs torch once (CPU wheel is fine).
voice:
	uv sync --inexact --extra audio --extra voice-build
	$(RUN) python -m research.voice.export --install

video-models:
	$(RUN) python scripts/video_models.py

doctor:
	$(RUN) python scripts/asr_check.py

demo-audio:
	$(RUN) --with piper-tts python scripts/make_replay_audio.py

lint:
	$(RUN) ruff check .
	$(RUN) ruff format --check .

fmt:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

typecheck:
	$(RUN) mypy

test:
	$(RUN) pytest

task:
	@if [ -z "$(T)" ]; then echo "Usage: make task T=T07"; exit 2; fi
	$(RUN) pytest --task $(T) -v

check: lint typecheck test
	@echo "make check: ALL GREEN"

run:
	$(RUN) uvicorn --app-dir src satyapan.api.app:app --reload --host 0.0.0.0 --port 8000

# Demo day: no --reload (a saved file must never restart the engine mid-call). 0.0.0.0 so the
# approver's phone on the same hotspot can open http://<laptop-ip>:8000/oob.
live:
	SATYAPAN_ASR_WARMUP=1 $(RUN) uvicorn --app-dir src satyapan.api.app:app --host 0.0.0.0 --port 8000

# The consumer journey: alerts speak to a person on their own call (docs/JUDGES.md §9).
live-personal:
	SATYAPAN_PROFILE=personal SATYAPAN_ASR_WARMUP=1 $(RUN) uvicorn --app-dir src satyapan.api.app:app --host 0.0.0.0 --port 8000

demo-data:
	$(RUN) python scripts/make_demo_data.py
	$(RUN) python scripts/export_schemas.py
	$(RUN) python scripts/decision_relevance.py

# Judges' kit / any files: one verdict per file, offline, nothing kept. make scan F=kit/
scan:
	$(RUN) python -m satyapan.check_cli $(F)

schemas:
	$(RUN) python scripts/export_schemas.py

status:
	@sed -n '/^| ID/,/^$$/p' docs/STATUS.md

judge:
	$(RUN) python scripts/judge_kit.py

dry-run:
	$(RUN) python scripts/dry_run.py

console-test:
	cd console && npm install && npm test

ext-test:
	cd extension && node --test tests/*.test.mjs

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache vault_data
