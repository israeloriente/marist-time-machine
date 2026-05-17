# InsightFace ONNX service (CPU). To enable CUDA, swap base image
# for nvidia/cuda runtime and replace onnxruntime with onnxruntime-gpu.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime deps for OpenCV + build deps for insightface's Cython extension.
# insightface 0.7.x ships no wheel for aarch64, so we compile it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        curl \
        build-essential \
        g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dep resolution
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
# Cython is needed at build time for insightface.thirdparty.face3d.mesh.cython
RUN uv pip install --system --no-cache cython numpy \
 && uv pip install --system --no-cache -r pyproject.toml \
 && apt-get purge -y --auto-remove build-essential g++ \
 && rm -rf /var/lib/apt/lists/* /root/.cache

COPY app/ ./app/

EXPOSE 8081

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
