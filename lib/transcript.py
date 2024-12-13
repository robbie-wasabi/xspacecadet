import json
from datetime import datetime, timezone
import logging
import os
import subprocess
from typing import Any, Dict, List

from lib.chatbot import Chatbot
from utils import convert_m4a_to_wav


def transcribe_wav(wav_path: str, transcript_path: str, hf_token: str):
    command = [
        "insanely-fast-whisper",
        "--file-name",
        wav_path,
        "--transcript-path",
        transcript_path,
        "--hf-token",
        hf_token,
    ]

    if os.name == "posix":
        command.extend(["--device-id", "mps"])

    return command


def transcribe_audio_and_write(audio_path: str, output_path: str, hf_token: str):
    """
    Transcribe audio and write to output path.
    """

    # ensure wav_path exists
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(
            f"audio file '{audio_path}' not found. Please record the space first."
        )

    # ensure wav_path is a wav file
    if audio_path.endswith(".m4a"):
        wav_path = audio_path.replace(".m4a", ".wav")
        convert_m4a_to_wav(audio_path, wav_path)
        audio_path = wav_path

    command = transcribe_wav(audio_path, output_path, hf_token)
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError:
        raise RuntimeError("Failed to generate transcript.")


def identify_speakers_in_transcript(transcript_json, space_data_json):

    # ensure transcript_json exists
    if not os.path.isfile(transcript_json):
        raise FileNotFoundError(f"Transcript file '{transcript_json}' not found.")

    # ensure space_data_json exists
    if not os.path.isfile(space_data_json):
        raise FileNotFoundError(f"Space data file '{space_data_json}' not found.")

    with open(transcript_json, "r") as f:
        transcript_data = json.load(f)

    with open(space_data_json, "r") as f:
        space_data = json.load(f)

    # space_start = space_data["started_at"]
    # space_joined = space_data["joined_at"]
    # space_join_buffer = space_joined - space_start
    space_frames = space_data["frames"].items()

    identified_speakers = {}

    for seg in transcript_data["speakers"]:
        seg_speaker = seg["speaker"]
        seg_timestamp = seg["timestamp"]
        logging.debug(f"identifying speaker {seg_speaker} in segment {seg_timestamp}")

        if seg_speaker in identified_speakers:
            logging.debug(
                f"speaker {seg_speaker} already identified as: {identified_speakers[seg_speaker]}\n"
            )
            continue

        # segments are timestamped in seconds relative to space start (I think)
        # UPDATE: turns out this assumption was wrong, it's relative to space joined
        # seg_start = int(space_joined + seg["timestamp"][0])
        # seg_end = int(space_joined + seg["timestamp"][1])
        seg_start = int(seg["timestamp"][0])
        seg_end = int(seg["timestamp"][1])

        # look for frames between seg_start and seg_end
        for i, frame in space_frames:
            frame_timestamp = frame["timestamp"]
            frame_speakers = frame["speakers"]

            # if frame_timestamp is not in the segment, skip
            if frame_timestamp < seg_start or frame_timestamp > seg_end:
                logging.debug(
                    f"Frame timestamp {frame_timestamp} not in segment {seg_start} to {seg_end}"
                )
                continue

            # if no speakers, skip
            if len(frame_speakers) == 0:
                logging.debug(f"No speakers in frame {i}, skipping")
                continue
            # if multiple speakers we cannot be certain, skip
            if len(frame_speakers) > 1:
                logging.debug(f"Multiple speakers in frame {i}, skipping")
                continue
            # if speaker already identified, skip
            if frame_speakers[0]["username"] in identified_speakers.values():
                logging.debug(
                    f"Speaker {frame_speakers[0]['username']} already identified, continuing"
                )
                continue

            # identify speaker in transcript
            identified_speakers[seg_speaker] = frame_speakers[0]["username"]
            logging.info(
                f"Identified speaker {seg_speaker} as {identified_speakers[seg_speaker]}\n"
            )
            break

    # Rewrite transcript with identified speakers
    for seg in transcript_data["speakers"]:
        seg_speaker = seg["speaker"]
        seg["speaker"] = identified_speakers.get(seg_speaker, "Unknown")

    # Save updated transcript
    updated_transcript_path = transcript_json.replace(".json", "_updated.json")
    with open(updated_transcript_path, "w") as f:
        json.dump(transcript_data, f, indent=2)

    logging.info("RESULTS:")
    logging.info(f"Identified speakers:\n")
    for speaker, username in identified_speakers.items():
        logging.info(f"  {speaker}: {username}")

    logging.info(f"Updated transcript saved to:")
    logging.info(f"  {updated_transcript_path}")

    return transcript_data


def consolidate_transcript(transcript_path: str) -> List[Dict[str, Any]]:

    # ensure transcript_path exists
    if not os.path.isfile(transcript_path):
        raise FileNotFoundError(f"Transcript file '{transcript_path}' not found.")

    with open(transcript_path, "r") as f:
        transcript_data = json.load(f)

    consolidated = []
    current_speaker = None
    current_text = ""
    current_start = None
    current_end = None

    for segment in transcript_data.get("speakers", []):
        speaker = segment.get("speaker")
        text = segment.get("text", "")
        start, end = segment.get("timestamp", (None, None))

        if speaker == current_speaker:
            current_text += f" {text}"
            current_end = end
        else:
            if current_speaker:
                consolidated.append(
                    {
                        "speaker": current_speaker,
                        "text": current_text.strip(),
                        "start": current_start,
                        "end": current_end,
                    }
                )
            current_speaker = speaker
            current_text = text
            current_start = start
            current_end = end

    # Add the last segment
    if current_speaker:
        consolidated.append(
            {
                "speaker": current_speaker,
                "text": current_text.strip(),
                "start": current_start,
                "end": current_end,
            }
        )

    return {"speakers": consolidated}


def gen_transcript_summary(transcript_path: str, openai_api_key: str):

    # ensure transcript_path exists
    if not os.path.isfile(transcript_path):
        raise FileNotFoundError(f"Transcript file '{transcript_path}' not found.")

    with open(transcript_path, "r") as f:
        transcript_data = json.load(f)

    try:
        chatbot = Chatbot(openai_api_key)
        summary = chatbot.generate_summary(transcript_data, "Please summarize the conversation.")
    except Exception as e:
        return f"Failed to generate transcript summary: {e}"
    return summary
