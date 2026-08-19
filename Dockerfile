FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY data ./data
COPY configs ./configs
COPY notes ./notes

RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir .

# CPU smoke only. vLLM is not in this image.
CMD ["python", "-m", "apertus_eval_prep", "eval", "--config", "configs/smoke.yaml", "--out", "results/smoke.json"]
