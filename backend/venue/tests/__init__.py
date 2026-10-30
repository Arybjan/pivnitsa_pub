import os

os.environ.setdefault(
    "JWT_SECRET_KEY", "venue-test-secret-key-with-at-least-32-characters"
)
os.environ.setdefault("DATABASE_URL", "sqlite://")
