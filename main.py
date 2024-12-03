import sys
import os
import time

from dotenv import load_dotenv
from utils import PATH_SPACE_DATA, PATH_TRANSCRIPT_UNIDENTIFIED, init_env, parse_space_id

load_dotenv()

import argparse
import os
import glob
import subprocess

from lib.transcript import identify_speakers_in_transcript
from lib.bot import XSpaceBot
from lib.xapi import XAPI


# print("cli is broken as of sep 25 2024")
# exit()


def record_space(
    space_id,
    x_cookie_file,
    x_bearer,
    headless,
    fetch_audio,
    fetch_space_metadata,
    take_screenshots,
    opts,
):
    parsed_opts = {}
    if opts:
        try:
            parsed_opts = dict(item.split("=") for item in opts.split(","))
        except ValueError:
            print("Warning: Invalid format for opts. Expected format: key1=value1,key2=value2")

    bot = XSpaceBot(x_cookie_file, space_id, x_bearer, headless=headless)
    try:
        bot.run(
            fetch_audio=fetch_audio,
            fetch_space_metadata=fetch_space_metadata,
            take_screenshots=take_screenshots,
            opts=parsed_opts,
        )
        # TODO: this is a hack to keep the main thread alive while the bot is running
        while not bot.stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping bot...")
        bot.stop()


#  diarizate and speech-to-text the audio file
def gen_recording_transcript(space_id, hf_token):
    transcript_json = PATH_TRANSCRIPT_UNIDENTIFIED.format(space_id=space_id)

    # TODO
    # with open(f"{space_dir}/space_data.json") as f:
    #     space_data = json.load(f)
    # started_at = space_data["started_at"]
    # joined_at = space_data["joined_at"]
    # start_time = dateutil_parser.isoparse(started_at.replace("Z", "+00:00"))
    # join_time = dateutil_parser.isoparse(joined_at.replace("Z", "+00:00"))
    # cut_time = (join_time - start_time).total_seconds()

    m4a = glob.glob(f"data/{space_id}/audio/*/audio_new.m4a")[0]
    wav = m4a.replace(".m4a", ".wav")

    if not os.path.isfile(wav) and os.path.isfile(m4a):
        os.system(f"ffmpeg -i {m4a} {wav}")
    elif not os.path.isfile(m4a):
        print(f"Audio file '{m4a}' not found. Exiting.")
        return

    command = [
        "insanely-fast-whisper",
        "--file-name",
        wav,
        "--transcript-path",
        transcript_json,
        "--hf-token",
        hf_token,
    ]

    if os.name == "posix":
        command.extend(["--device-id", "mps"])

    subprocess.run(command)


# identify users in transcript using captured frames from the space
def identify_transcript_speakers(space_id):
    transcript_json = PATH_TRANSCRIPT_UNIDENTIFIED.format(space_id=space_id)
    space_data_json = PATH_SPACE_DATA.format(space_id=space_id)
    return identify_speakers_in_transcript(transcript_json, space_data_json)


def transcribe_and_identify_speakers(space_id, hf_token):
    gen_recording_transcript(space_id, hf_token)
    return identify_transcript_speakers(space_id)


def fetch_space_metadata(space_id, x_bearer):
    xapi = XAPI(x_bearer)
    try:
        metadata = xapi.get_space_metadata(space_id)
        print(metadata)
    except Exception as e:
        print(f"Failed to fetch space metadata: {str(e)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="XSpaceCadet CLI")
    subparsers = parser.add_subparsers(dest="command")

    # record command
    record_parser = subparsers.add_parser("record", help="capture a space")
    record_parser.add_argument("space", type=str, help="space id")
    record_parser.add_argument("cookie_file", type=str, nargs="?", help="path to x cookie file")
    record_parser.add_argument(
        "--no-headless",
        action="store_true",
        dest="no_headless",
        default=False,
        help="run the bot in non-headless mode (shows selenium browser)",
    )

    # download audio from the space
    # on by default. needed for transcript generation later
    record_parser.add_argument(
        "--no-audio",
        dest="no_audio",
        action="store_true",
        default=False,
        help="do not fetch audio from the space (useful for debugging)",
    )

    # fetch x space metadata: name, topic, description, hosts, etc... (requires X Basic API access)
    # on by default. needed to automatically identify speakers from transcript
    record_parser.add_argument(
        "--no-metadata",
        dest="no_metadata",
        action="store_true",
        default=False,
        help="do not fetch space metadata (if you don't have X Basic API access)",
    )

    # take screenshots of selenium browser
    # off by default. useful for debugging
    record_parser.add_argument(
        "--take_screenshots",
        action="store_true",
        default=False,
        help="take screenshots from the space (useful for debugging)",
    )
    record_parser.add_argument("--opts", type=str, help="options for the bot", default=None)

    # process command
    gen_transcript_parser = subparsers.add_parser(
        "gen-transcript", help="diarize and transcribe audio"
    )
    gen_transcript_parser.add_argument("space", type=str, help="space id")
    gen_transcript_parser.add_argument(
        "hf_token",
        type=str,
        nargs="?",
        help="Hugging Face token",
    )

    # identify command
    id_users_parser = subparsers.add_parser(
        "id-speakers", help="identify users in a space transcript"
    )
    id_users_parser.add_argument("space", type=str, help="space id")

    # fetch space metadata command
    fetch_metadata_parser = subparsers.add_parser("fetch-metadata", help="fetch space metadata")
    fetch_metadata_parser.add_argument("space", type=str, help="space id")
    fetch_metadata_parser.add_argument("x_bearer", type=str, nargs="?", help="X API bearer token")

    # initialize environment variables
    hf_token, x_bearer, x_cookie, missing = init_env()
    if missing:
        print(f"Missing environment variables: {missing}")
        exit()

    transcribe_parser = subparsers.add_parser("transcribe", help="transcribe and identify speakers")
    transcribe_parser.add_argument("space", type=str, help="space id")
    transcribe_parser.add_argument(
        "hf_token",
        type=str,
        nargs="?",
        help="Hugging Face token",
    )

    # parse arguments and override environment variables
    args = parser.parse_args()
    space_id = parse_space_id(args.space)

    if args.command == "record":
        if args.cookie_file:
            x_cookie = args.cookie_file

    command_functions = {
        "record": lambda: record_space(
            space_id,
            x_cookie,
            x_bearer,
            not args.no_headless,
            not args.no_audio,
            not args.no_metadata,
            args.take_screenshots,
            args.opts,
        ),
        "gen-transcript": lambda: gen_recording_transcript(space_id, hf_token),
        "id-speakers": lambda: identify_transcript_speakers(space_id),
        "transcribe": lambda: transcribe_and_identify_speakers(space_id, hf_token),
        "fetch-metadata": lambda: fetch_space_metadata(space_id, x_bearer),
    }

    command_functions[args.command]()
