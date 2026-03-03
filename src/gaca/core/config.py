"""Runtime configuration with feature detection."""

import os
import subprocess


class Config:
    """SEO GACA runtime configuration — detects available features."""

    @property
    def has_dataforseo(self) -> bool:
        return bool(os.getenv("DATAFORSEO_LOGIN") and os.getenv("DATAFORSEO_PASSWORD"))

    @property
    def has_lighthouse(self) -> bool:
        try:
            result = subprocess.run(
                ["npx", "lighthouse", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @property
    def has_smtp(self) -> bool:
        return bool(os.getenv("SMTP_HOST"))

    @property
    def data_dir(self) -> str:
        return os.getenv("GACA_DATA_DIR", os.path.expanduser("~/.gaca"))

    def status(self) -> dict:
        return {
            "lighthouse": self.has_lighthouse,
            "dataforseo": self.has_dataforseo,
            "smtp": self.has_smtp,
            "data_dir": self.data_dir,
        }


config = Config()
