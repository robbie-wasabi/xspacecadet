import glob
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
from dotenv import load_dotenv

from lib.bot import XSpaceBot
from lib.chatbot import Chatbot
from lib.transcript import (
    consolidate_transcript,
    gen_transcript_summary,
    identify_speakers_in_transcript,
    transcribe_audio_and_write,
)
from utils import (
    PATH_AUDIO_M4A,
    PATH_SPACE_DATA,
    PATH_TRANSCRIPT_UNIDENTIFIED,
    PATH_TRANSCRIPT_CONSOLIDATED,
    PATH_TRANSCRIPT_SUMMARY,
    PATH_TRANSCRIPT_IDENTIFIED,
    load_json_file,
    load_text_file,
    save_json_file,
    save_text_file,
    parse_space_id,
)


# Load environment variables from .env file
load_dotenv()


def read_space_metadata(space_id: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    space_dir = f"data/{space_id}"
    space_data_path = os.path.join(space_dir, "space_data.json")

    space_data = load_json_file(space_data_path)
    if not space_data:
        return None

    started_at = datetime.fromtimestamp(space_data.get("started_at", 0))
    joined_at = datetime.fromtimestamp(space_data.get("joined_at", 0))

    return {
        "id": space_data.get("id", "Unknown"),
        "title": space_data.get("title", "Unknown"),
        "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        "joined_at": joined_at.strftime("%Y-%m-%d %H:%M:%S"),
        "frames_captured": len(space_data.get("frames", {})),
        "summary_path": os.path.join(space_dir, "transcript_summary.txt"),
        "transcript_path": os.path.join(space_dir, "transcript_updated.json"),
    }


def start_recording(
    space_id: str,
    x_cookie_file: str,
    x_bearer: str,
    headless: bool,
    fetch_audio: bool,
    fetch_space_metadata: bool,
    take_screenshots: bool,
    options: Dict[str, Any],
) -> Optional[str]:
    if "bot" in st.session_state:
        return "A recording session is already running."

    bot = XSpaceBot(x_cookie_file, space_id, x_bearer, headless=headless)
    st.session_state.bot = bot

    bot.run(
        fetch_audio=fetch_audio,
        fetch_space_metadata=fetch_space_metadata,
        take_screenshots=take_screenshots,
        opts=options,
    )


def stop_recording_session() -> Optional[str]:
    bot = st.session_state.get("bot")
    if bot:
        bot.stop()
        del st.session_state.bot
    else:
        return "No active recording session to stop."


def transcribe(space_id: str, hf_token: str, openai_api_key: str) -> None:
    """
    Transcribe space audio and generate transcripts.
    """
    space_data_path = PATH_SPACE_DATA.format(space_id=space_id)
    unidentified_path = PATH_TRANSCRIPT_UNIDENTIFIED.format(space_id=space_id)
    identified_path = PATH_TRANSCRIPT_IDENTIFIED.format(space_id=space_id)
    consolidated_path = PATH_TRANSCRIPT_CONSOLIDATED.format(space_id=space_id)
    summary_path = PATH_TRANSCRIPT_SUMMARY.format(space_id=space_id)
    audio_path = PATH_AUDIO_M4A.format(space_id=space_id)

    # TODO
    # audio_files = glob.glob(f"data/{space_id}/audio/*/audio_new.m4a")
    # if not audio_files:
    #     return False, "No audio files found. Please record the space first."
    # m4a = audio_files[0]
    # wav = m4a.replace(".m4a", ".wav")

    try:
        transcribe_audio_and_write(audio_path, unidentified_path, hf_token)
    except Exception as e:
        st.error(f"Failed to transcribe space audio: {e}")
        return

    try:
        identified_transcript = identify_speakers_in_transcript(unidentified_path, space_data_path)
        save_json_file(
            identified_transcript,
            identified_path,
        )
    except Exception as e:
        st.error(f"Failed to identify speakers in transcript: {e}")
        return

    try:
        consolidated_transcript = consolidate_transcript(identified_path)
        save_json_file(consolidated_transcript, consolidated_path)
    except Exception as e:
        st.error(f"Failed to consolidate transcript: {e}")
        return

    try:
        summary = gen_transcript_summary(consolidated_path, openai_api_key)
        save_text_file(summary, summary_path)
    except Exception as e:
        st.error(f"Failed to generate transcript summary: {e}")
        return


def validate_environment(x_bearer: str, x_cookie: str, hf_token: str) -> bool:
    if not all([x_bearer, x_cookie, hf_token]):
        return False
    return True


def main() -> None:
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(initial_sidebar_state="collapsed")

    st.title("X SpaceCadet")
    st.sidebar.header("Configuration")

    # Retrieve environment variables
    env_x_bearer = os.getenv("X_BEARER", "")
    env_x_cookie = os.getenv("X_COOKIE_FILE", "")
    env_hf_token = os.getenv("HF_TOKEN", "")
    env_openai_api_key = os.getenv("OPENAI_API_KEY", "")

    # Input fields with placeholders from environment variables
    hf_token = st.sidebar.text_input(
        "Hugging Face Token",
        type="password",
        placeholder="Enter Hugging Face Token",
        value=env_hf_token,
    )
    x_bearer = st.sidebar.text_input(
        "X Bearer Token", placeholder="Enter X Bearer Token", value=env_x_bearer
    )
    x_cookie = st.sidebar.text_input(
        "Path to X Cookie File",
        placeholder="Enter path to X Cookie File",
        value=env_x_cookie,
    )
    openai_api_key = st.sidebar.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="Enter OpenAI API Key",
        value=env_openai_api_key,
    )

    # Replace the menu and choice with tabs
    record_tab, transcribe_tab = st.tabs(["Record Space", "Transcribe"])

    # Initialize session state
    # if "recording_in_progress" not in st.session_state:
    st.session_state.recording_in_progress = False

    with record_tab:
        space_id = parse_space_id(st.text_input("Space ID", help="Enter space ID or URL"))
        with st.expander("Advanced Options"):
            headless = st.checkbox("Headless Mode", value=True)
            take_screenshots = st.checkbox("Take Screenshots", value=False)

        options = {}

        if st.button("Record"):
            if not validate_environment(x_bearer, x_cookie, hf_token):
                st.error(
                    "Please provide X Bearer Token, X Cookie File path, and Hugging Face Token."
                )
            elif not space_id:
                st.error("Please provide a Space ID.")
            else:
                err = start_recording(
                    space_id=space_id,
                    x_cookie_file=x_cookie,
                    x_bearer=x_bearer,
                    headless=headless,
                    fetch_audio=True,
                    fetch_space_metadata=True,
                    take_screenshots=take_screenshots,
                    options=options,
                )
                if err:
                    st.write(err)
                if not err:
                    st.write("Recording in progress...")
                    st.session_state.recording_in_progress = True

        if st.button("Stop Recording"):
            err = stop_recording_session()
            if err:
                st.write(err)
            if not err:
                st.write("Recording stopped.")
                st.session_state.recording_in_progress = False

    with transcribe_tab:
        # ensure that data folder exists
        if not os.path.exists("data"):
            st.error("No data folder found. Please record a space first.")
            return

        dirs = os.listdir("data")
        space_ids = []
        for dir in dirs:
            full_path = os.path.join("data", dir)
            if os.path.isdir(full_path):
                space_ids.append(dir)

        space_titles = ["None"]
        for space_id in space_ids:
            metadata = read_space_metadata(space_id)
            if metadata:
                title = metadata["title"]
                space_titles.append(f"{space_id}: {title}")

        selected_space_title = st.selectbox("Select a previously captured space:", space_titles)
        selected_space = (
            selected_space_title.split(":")[0].strip() if selected_space_title != "None" else None
        )

        metadata = read_space_metadata(selected_space) if selected_space else None

        if selected_space and metadata:
            st.write(f"**Title:** {metadata['title']}")
            st.write(f"**Started at:** {metadata['started_at']}")
            st.write(f"**Joined at:** {metadata['joined_at']}")
            st.write(f"**Frames captured:** {metadata['frames_captured']}")
            st.write(f"**Transcript path:** {metadata['transcript_path']}")
        elif selected_space:
            st.write("No metadata available for this space.")

        if st.button("Transcribe"):
            if not all([selected_space, hf_token]):
                st.error("Please provide Space ID and Hugging Face Token.")
            else:
                transcribe(selected_space, hf_token, openai_api_key)

        if os.path.exists(PATH_TRANSCRIPT_UNIDENTIFIED.format(space_id=selected_space)):
            with st.expander("View Raw Transcript"):
                st.json(
                    load_json_file(PATH_TRANSCRIPT_UNIDENTIFIED.format(space_id=selected_space))
                )

        if os.path.exists(PATH_TRANSCRIPT_IDENTIFIED.format(space_id=selected_space)):
            with st.expander("View Updated Transcript"):
                st.json(load_json_file(PATH_TRANSCRIPT_IDENTIFIED.format(space_id=selected_space)))

        if os.path.exists(PATH_TRANSCRIPT_CONSOLIDATED.format(space_id=selected_space)):
            with st.expander("View Consolidated Transcript"):
                st.json(
                    load_json_file(PATH_TRANSCRIPT_CONSOLIDATED.format(space_id=selected_space))
                )

        if os.path.exists(PATH_TRANSCRIPT_SUMMARY.format(space_id=selected_space)):
            with st.expander("View Summary"):
                st.write(load_text_file(PATH_TRANSCRIPT_SUMMARY.format(space_id=selected_space)))

        #     st.warning("Run 'Transcribe' to generate a transcript from recording.")
        # else:
        #     st.info("Please select a space with a transcript to view.")

    # Control sidebar
    st.sidebar.markdown("---")
    st.sidebar.header("Control")
    if st.sidebar.button("Shutdown Recording Session"):
        success, err = stop_recording_session()
        st.write(err)


if __name__ == "__main__":
    main()
