# Satyapan x Pramaan — offline multimedia forensic workstation.
#
# Deliberately small: the app must run with no network at run time. The large optional models
# (GenD CLIP ViT-L/14 1.2 GB, XLS-R voice 1.3 GB) are NOT baked in; without them the engines
# abstain where they must and the pixel, metadata, C2PA, custody and report paths all still run.
# Mount models/ into /app/models and pass --heavy flags (or set SATYAPAN_HEAVY=1) to use them.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SATYAPAN_FORENSIC_CASES_DIR=/data/cases

# ffmpeg decodes audio/video for the forensic engines; libgomp is needed by onnxruntime wheels.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install . \
    && pip install "pillow>=10" "numpy>=1.26" "cryptography>=42" \
                   "opencv-python-headless>=4.9" "av>=12"

COPY demo_kit ./demo_kit
COPY scripts/forensic_demo.py scripts/make_forensic_demo_kit.py ./scripts/

RUN mkdir -p /data/cases

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Bind on all interfaces inside the container only; nothing here makes an outbound connection.
CMD ["uvicorn", "--app-dir", "src", "satyapan.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
