import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional, Tuple

DIR_SPACE = "data/{space_id}"
PATH_AUDIO_M4A = f"{DIR_SPACE}/audio.m4a"
PATH_AUDIO_WAV = f"{DIR_SPACE}/audio.wav"
PATH_FRAMES = f"{DIR_SPACE}/frames"
PATH_TRANSCRIPT_UNIDENTIFIED = f"{DIR_SPACE}/transcript.json"
PATH_TRANSCRIPT_IDENTIFIED = f"{DIR_SPACE}/transcript_updated.json"
PATH_TRANSCRIPT_CONSOLIDATED = f"{DIR_SPACE}/transcript_consolidated.json"
PATH_TRANSCRIPT_SUMMARY = f"{DIR_SPACE}/transcript_summary.txt"
PATH_SPACE_DATA = f"{DIR_SPACE}/space_data.json"


def read_env_file(file_path):
    with open(file_path, "r") as file:
        return file.read()


def write_env_file(file_path, content):
    with open(file_path, "w") as file:
        file.write(content)


# hf_token, x_bearer, x_cookie_file, missing_vars
def init_env():
    env_vars = ["HF_TOKEN", "X_BEARER", "X_COOKIE_FILE"]
    values = {var: os.getenv(var) for var in env_vars}
    missing = [var for var, value in values.items() if not value]

    return values["HF_TOKEN"], values["X_BEARER"], values["X_COOKIE_FILE"], missing


def load_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r") as file:
        return json.load(file)


def save_json_file(data: Any, file_path: str) -> None:
    with open(file_path, "w") as file:
        json.dump(data, file, indent=2)


def load_text_file(file_path: str) -> Optional[str]:
    if not os.path.exists(file_path):
        return None

    with open(file_path, "r") as file:
        return file.read()


def save_text_file(text: str, file_path: str) -> None:
    with open(file_path, "w") as file:
        file.write(text)


# TODO: ideally we wouldn't use a subprocess like this
def convert_m4a_to_wav(m4a_path: str, wav_path: str) -> bool:
    """
    Convert an M4A audio file to WAV format using ffmpeg.

    Args:
        m4a_path (str): Path to the M4A file.
        wav_path (str): Path to save the WAV file.

    Returns:
        bool: True if conversion was successful, False otherwise.
    """
    try:
        subprocess.run(["ffmpeg", "-i", m4a_path, "-y", wav_path], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def parse_space_id(space):
    url_pattern = re.compile(r"https://x\.com/i/spaces/([a-zA-Z0-9]+)(/peak)?")
    match = url_pattern.match(space)
    if match:
        return match.group(1)
    return space
