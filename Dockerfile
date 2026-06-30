FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates curl \
    fonts-liberation \
  && rm -rf /var/lib/apt/lists/*

# Ensure setuptools
RUN python -m pip install --no-cache-dir --upgrade "pip==26.0.1" "wheel" "setuptools==70.3.0"
## Hard fail if pkg_resources missing
RUN python -c "import setuptools, pkg_resources; print('OK', setuptools.__version__)"

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .
CMD ["python3", "app.py"]