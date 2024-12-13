from datetime import datetime
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from PIL import Image
import io
from time import sleep
import threading
import os
from twspace_dl import Twspace
import urllib3

from twspace_dl.cookies import load_cookies
from twspace_dl.api import API

import logging

# from twspace_dl.twspace_dl import TwspaceDL
# from lib.wrapped_twspace_dl import WrappedTwspaceDL
from lib.twspace_dl import TwspaceDL

from .xapi import XAPI

from webdriver_manager.chrome import ChromeDriverManager


# from .helpers import animation_above_threshold, parse_space_id

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# TODO: broadcasts

SPACE_JSON = "space_data.json"

# we can use data urls from the animated speaker canvas to determine if a user is speaking
# since the canvas has a transparent bg, we can generally assume that the longer the data url,
# the more likely that the user is speaking. this isn't perfect but it's a start. moreover,
# x users often mute and unmute, so this is a simple heuristic to filter out the silent frames
DATA_URL_EMPTY = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAC1JREFUWEft0EERAAAAAUH6lxbDZxU4s815PffjAAECBAgQIECAAAECBAgQIDAaPwAh6O5R/QAAAABJRU5ErkJggg=="
DATA_URL_NOT_SPEAKING = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAAXNSR0IArs4c6QAAAMRJREFUWEftlkESgjAMRX+8mHAJ9CjdIbseRb0E5WLGCR0YkcTpximLdP35/+elDBAqH6qcDy/gBJyAE3ACxyAQrtyA0YMxxSfdrO/Dh64BMBRqJ/GztBQ6lsB+DSWk+KBWKxEuPIIh4csxS4SOeeNxQhvvlL59pcBWKApFPE//wrgxMMruhpKHDC0pU5UXyGh390j1NFb2lxVotLSiGQyAFRkhgTBou1rQz1rCuUiXE35qj/Ea1vwtcwJOwAk4ASdQncAb839mISC0yNAAAAAASUVORK5CYII="
DATA_URL_MAYBE_SPEAKING = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAJFJREFUOE/FkkEOgyAQRf/3YsVL2B6FnbDjKNVLyMkcAy2JaRCDpJEt/DdvhiEaDxvzaAfolyisUG6mObPJvaUeRGKQ8G5ifwT5hpd436F3b/oY+xsgVExVQqUqAz1ImMe4b6sO8JQFAnUZEJWDRQef2qgyyP3EMSDpAra0CyUDA+IBwu6nnrX4aeuzPo3nfsAGQiaBEfCZ9OsAAAAASUVORK5CYII="


def animation_above_threshold(data_url):
    # TODO: improve this heuristic
    # 273 is the estimated length of the base64 encoded data url for a speaking user. we use this
    # heuristic to filter out silent frames but can be improved upon. we used to try to compare to
    # DATA_URL_NOT_SPEAKING but it seems X changes the length of the data url every so often.
    if len(data_url) <= 273:
        return False
    return True


class XSpaceBot:
    def __init__(self, x_cookie_file, space_id, x_bearer, headless=True):
        logging.debug("XSpaceBot init:")
        logging.debug(f"x_cookie_file: {x_cookie_file}")
        logging.debug(f"cookie file exists: {os.path.exists(x_cookie_file)}")
        logging.debug(f"space_id: {space_id}")
        logging.debug(f"x_bearer: {x_bearer}")
        logging.debug(f"headless: {headless}")

        self.http = urllib3.PoolManager(maxsize=10)
        self.x_api = XAPI(x_bearer)
        self.x_cookie_file = x_cookie_file
        self.space_id = space_id
        self.space_url = f"https://x.com/i/spaces/{space_id}"
        self.driver = None
        self.stop_event = threading.Event()
        self.headless = headless

        self.threads = []  # Track all threads

        # create space output folder
        self.output_dir = os.path.join(os.getcwd(), "data", f"{space_id}")
        os.makedirs(self.output_dir, exist_ok=True)

        # space data json file
        self.space_data_json_file = os.path.join(self.output_dir, SPACE_JSON)

        # create frames folder
        self.captured_frames_dir = os.path.join(self.output_dir, "frames")
        os.makedirs(self.captured_frames_dir, exist_ok=True)

        # create audio folder
        self.downloaded_audio_dir = os.path.join(self.output_dir, "audio")

        # init TwspaceDL
        API.init_apis(load_cookies(self.x_cookie_file))
        twspace = Twspace.from_space_url(self.space_url)
        # self.twspace_dl = WrappedTwspaceDL(twspace, "audio")
        self.twspace_dl = TwspaceDL(twspace, "audio")
        self.twspace_dl_thread = None

        self.joined_space_at = None

    def run(self, fetch_space_metadata=True, fetch_audio=True, take_screenshots=False, opts={}):
        logger.info("running...")

        print("fetch_space_metadata", fetch_space_metadata)

        # create space data json file
        self._create_space_data_json_file()

        if fetch_space_metadata:
            # fetch space metadata and write to json file
            try:
                space_data = self.x_api.get_space_metadata(self.space_id)
            except Exception as e:
                logger.error(f"Failed to fetch space metadata: {str(e)}")
                self._shutdown()
                return

            logger.info(f"Space data: {space_data}")
            print(f"Space data: {space_data}")
            # Convert started_at to unix timestamp
            if "started_at" in space_data:
                started_at = datetime.fromisoformat(space_data["started_at"])
                space_data["started_at"] = int(started_at.timestamp())
            if space_data is not None:
                with open(self.space_data_json_file, "w") as f:
                    json.dump(space_data, f, indent=2)
                logger.info(f"Space data written to {self.space_data_json_file}")
            else:
                logger.error("Failed to fetch space metadata. space_data is None.")
                self._shutdown()

        # TODO: check if space has ended

        # set up selenium driver
        self._setup_webdriver()

        # browser open x.com
        logger.info("opening x.com...")
        self.driver.get("https://x.com")

        # browser login with cookies
        logger.info("loading cookies...")
        try:
            self._load_cookies()
        except:
            self._shutdown()

        # browser navigate to the space
        logger.info("joining space...")
        self.driver.get(self.space_url)

        # browser check if the space ended UI is shown
        if self._get_button("Play recording", timeout=10):
            logger.info("Space has ended. Quitting.")
            self._shutdown()
            return

        # browser click the join button
        if start_listening_btn := self._get_button("Start listening", timeout=10):
            start_listening_btn.click()
            self.joined_space_at = int(time.time())
            self._update_space_data("joined_at", self.joined_space_at)
        else:
            logger.error("Failed to join the X Space. The join button was not found.")
            self._shutdown()
            return

        # sometimes there is an acknowledgement button that needs to be clicked
        def dismiss_got_it():
            while not self.stop_event.is_set():
                try:
                    if got_it_btn := self._get_button("Got it"):
                        got_it_btn.click()
                except:
                    pass
                sleep(10)

        # Start the dismiss_got_it thread
        dismiss_thread = threading.Thread(target=dismiss_got_it, daemon=True)
        dismiss_thread.start()
        self.threads.append(dismiss_thread)

        # Start the download_space_audio thread if fetching audio
        if fetch_audio:
            self.twspace_dl_thread = threading.Thread(
                target=self._download_space_audio, daemon=True
            )
            self.twspace_dl_thread.start()
            self.threads.append(self.twspace_dl_thread)

        # Start the capture_speaker_data thread
        capture_thread = threading.Thread(
            target=self._capture_speaker_data, args=(opts.get("speaker_data_fps", 1),), daemon=True
        )
        capture_thread.start()
        self.threads.append(capture_thread)

        # Optionally start the capture_webdriver_frames thread
        if take_screenshots:
            screenshot_fps = opts.get("screenshot_fps", 1)
            screenshot_thread = threading.Thread(
                target=self._capture_webdriver_frames, args=(screenshot_fps,), daemon=True
            )
            screenshot_thread.start()
            self.threads.append(screenshot_thread)

        # try:
        #     # Wait for all threads to complete
        #     for thread in self.threads:
        #         thread.join()
        # except KeyboardInterrupt:
        #     logger.info("Keyboard interrupt received. Shutting down...")
        #     self._shutdown()
        # finally:
        #     logger.info("All threads completed. Shutting down...")
        #     self._shutdown()

        logger.info("XSpaceBot run completed.")

    # Stop all threads and quit the driver
    def stop(self):
        self._shutdown()

    def _shutdown(self):
        logger.info("Initiating shutdown...")
        self.stop_event.set()  # Signal all threads to stop

        self.twspace_dl.cancel_download()

        # Wait for all threads to finish with a timeout
        # for thread in self.threads:
        #     thread_name = thread.name if hasattr(thread, "name") else "Unknown"
        #     logger.info(f"Waiting for thread {thread_name} to finish...")
        #     thread.join(timeout=5)  # 5 second timeout
        #     if thread.is_alive():
        #         logger.warning(f"Thread {thread_name} did not finish in time.")

        # Quit the Selenium driver
        if self.driver:
            logger.info("Quitting Selenium driver...")
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error quitting Selenium driver: {e}")

        logger.info("Shutdown complete.")

    # Set up the selenium driver
    def _setup_webdriver(self):
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--mute-audio")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        # TODO: make this frame longer to capture more speakers without having to scroll
        options.add_argument("--window-size=375,2000")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1"
        )

        # Use Service class to set up ChromeDriver
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

    # Load cookies into the selenium driver
    def _load_cookies(self):
        try:
            with open(self.x_cookie_file, "r") as f:
                cookies = f.readlines()
        except FileNotFoundError:
            logger.error(f"cookie file not found: {self.x_cookie_file}")
            raise
        except Exception as e:
            logger.error(f"Error loading cookies: {e}")
            raise

        for cookie in cookies:
            fields = cookie.strip().split("\t")
            if len(fields) >= 7:
                cookie_dict = {
                    "name": fields[5],
                    "value": fields[6],
                    "domain": fields[0],
                    "path": fields[2],
                    "expires": int(fields[4]) if fields[4].isdigit() else None,
                    "secure": fields[3] == "TRUE",
                }
                self.driver.add_cookie(cookie_dict)

    # Capture and save webdriver frames at a specified frame rate
    def _capture_webdriver_frames(self, fps=1):
        try:
            logger.info("recording frames...")
            frame_number = 0
            buffer = []
            interval = 1 / fps

            def save_frames():
                while not self.stop_event.is_set():
                    if buffer:
                        frame_data = buffer.pop(0)
                        frame_data[0].save(
                            os.path.join(self.captured_frames_dir, f"{frame_data[1]:05d}.png")
                        )

            threading.Thread(target=save_frames, daemon=True).start()

            while not self.stop_event.is_set():
                start_time = time.time()

                screenshot = self.driver.get_screenshot_as_png()
                image = Image.open(io.BytesIO(screenshot))
                buffer.append((image, frame_number))
                frame_number += 1

                # Calculate sleep time to maintain desired fps
                elapsed_time = time.time() - start_time
                sleep_time = max(0, interval - elapsed_time)
                time.sleep(sleep_time)
        except Exception as e:
            logger.error(f"failed to capture frames: {e}")
            raise

    # capture and save which users are speaking at a specified fps
    def _capture_speaker_data(self, fps=1):
        try:
            logger.info("recording speaker data...")
            frame_number = 0
            interval = 1 / fps
            frame_batch_buffer = {}

            def write_batch():
                while not self.stop_event.is_set():
                    if frame_batch_buffer:
                        with self.batch_lock:
                            frame_batch = frame_batch_buffer.copy()
                            frame_batch_buffer.clear()
                        self._update_space_data_frames(frame_batch)
                    time.sleep(1)  # Adjust sleep time as needed

            # Start the batch writing thread
            self.batch_lock = threading.Lock()
            threading.Thread(target=write_batch, daemon=True).start()
            self.threads.append(threading.current_thread())  # Track the write_batch thread

            while not self.stop_event.is_set():
                capture_started_at = time.time()

                speaking_elements = self.driver.find_elements(
                    By.XPATH,
                    "//div[@id='ParticipantsWrapper']//div[contains(@class, 'css-175oi2r') and contains(@class, 'r-1awozwy') and contains(@class, 'r-6koalj') and contains(@class, 'r-18u37iz') and contains(@class, 'r-1777fci')]",
                )

                speaker_data = {
                    "timestamp": int(time.time()) - self.joined_space_at,  # Use relative timestamp
                    "speakers": [],
                }
                if speaking_elements:
                    print(f"speaking_elements: {speaking_elements}")
                    for speaking_elem in speaking_elements:
                        try:
                            canvas = speaking_elem.find_element(By.TAG_NAME, "canvas")
                            if not canvas:
                                continue

                            data_url = self.driver.execute_script(
                                "return arguments[0].toDataURL('image/png');", canvas
                            )

                            # TODO: we should be able to determine how likely a user is to be speaking
                            # by how much their canvas is filling the screen
                            if not animation_above_threshold(data_url):
                                continue

                            # Fetch the username
                            try:
                                username_elem = speaking_elem.find_element(
                                    By.XPATH,
                                    "./ancestor::div[contains(@class, 'css-175oi2r') and contains(@class, 'r-1awozwy')]"
                                    "//span[contains(@class, 'css-1jxf684') and contains(@class, 'r-poiln3')]",
                                )
                                username = (
                                    username_elem.text.strip() if username_elem else "Unknown"
                                )
                            except Exception as e:
                                logger.error(f"Failed to retrieve username: {e}")
                                username = "Unknown"

                            speaker = {
                                # TODO: we should be able to determine how likely a user is to be speaking
                                # by how much their canvas is filling the screen
                                "username": username,
                            }
                            speaker_data["speakers"].append(speaker)
                        except Exception as e:
                            logger.error(f"Failed to capture canvas data: {e}")

                with self.batch_lock:
                    frame_batch_buffer[str(frame_number)] = speaker_data

                frame_number += 1

                # Calculate sleep time to maintain desired fps
                elapsed_time = time.time() - capture_started_at
                sleep_time = max(0, interval - elapsed_time)
                time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"failed to capture speaker data: {e}")
            raise

    # Download space audio using twspace_dl
    # if the space is already running, the audio will be downloaded from the live stream
    # starting from the joined_at timestamp
    def _download_space_audio(self):
        try:
            logger.info("downloading audio...")
            # current_dir = os.getcwd()
            # os.makedirs(self.downloaded_audio_dir, exist_ok=True)
            # os.chdir(self.downloaded_audio_dir)

            while not self.stop_event.is_set():
                self.twspace_dl.download(self.output_dir)

            # os.chdir(current_dir)
        except Exception as e:
            logger.error(f"failed to download audio: {e}")
            raise

    # Get a button element by its text
    def _get_button(self, button_text, timeout):
        try:
            locator = (By.XPATH, f"//span[contains(text(), '{button_text}')]")
            if timeout:
                return WebDriverWait(self.driver, timeout).until(
                    EC.element_to_be_clickable(locator)
                )
            return self.driver.find_element(*locator)
        except TimeoutException:
            return None

    # Create space data json file
    def _create_space_data_json_file(self):
        with open(self.space_data_json_file, "w") as f:
            json.dump({}, f, indent=2)

    # Update space data json file
    def _update_space_data(self, key, value):
        with open(self.space_data_json_file, "r") as f:
            space_data = json.load(f)
        space_data[key] = value
        with open(self.space_data_json_file, "w") as f:
            json.dump(space_data, f, indent=2)
        # logger.info(f"Updated space data with {key}: {value}")

    # Update space data json file in batches
    def _update_space_data_frames(self, frame_batch_data):
        logging.info(frame_batch_data)
        with open(self.space_data_json_file, "r+") as f:
            space_data = json.load(f)
            if "frames" not in space_data:
                space_data["frames"] = {}
            space_data["frames"].update(frame_batch_data)
            f.seek(0)
            json.dump(space_data, f, indent=2)
            f.truncate()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run XSpaceBot")
    parser.add_argument("--cookie-file", required=True, help="Path to the X cookie file")
    parser.add_argument("--space-id", required=True, help="ID of the space to join")
    parser.add_argument("--bearer", required=True, help="X API bearer token")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--fetch-metadata", action="store_true", help="Fetch space metadata")
    parser.add_argument("--fetch-audio", action="store_true", help="Fetch space audio")
    parser.add_argument(
        "--take-screenshots", action="store_true", help="Take screenshots of the space"
    )
    parser.add_argument(
        "--speaker-fps", type=int, default=1, help="Frames per second for speaker data"
    )
    parser.add_argument(
        "--screenshot-fps", type=int, default=1, help="Frames per second for screenshots"
    )

    args = parser.parse_args()

    bot = XSpaceBot(
        x_cookie_file=args.cookie_file,
        space_id=args.space_id,
        x_bearer=args.bearer,
        headless=args.headless,
    )

    try:
        bot.run(
            fetch_space_metadata=args.fetch_metadata,
            fetch_audio=args.fetch_audio,
            take_screenshots=args.take_screenshots,
            opts={"speaker_data_fps": args.speaker_fps, "screenshot_fps": args.screenshot_fps},
        )
        # Keep the main thread alive while bot is running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
        bot._shutdown()
