import os
import threading
import time
import unittest

from lib.bot import XSpaceBot
from utils import init_env


class TestXSpaceBotShutdownIntegration(unittest.TestCase):
    def setUp(self):
        # Change to the project root directory
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.chdir(project_root)

        # Now call init_env() which should find the .env file
        x_cookie = "x_cookies.txt"
        x_bearer = os.getenv("X_BEARER")
        self.bot = XSpaceBot(
            x_cookie_file=x_cookie,
            space_id="1gqxvNMdRPRxB",
            x_bearer=x_bearer,
            headless=True,
        )

        # Ensure stop_event is cleared before starting
        self.bot.stop_event.clear()

    def test_shutdown_real_download(self):
        # Capture logs
        with self.assertLogs(level="DEBUG") as captured_logs:
            # download_thread = threading.Thread(
            #     target=self.bot._download_space_audio, daemon=True, name="DownloadSpaceAudioThread"
            # )
            # download_thread.start()
            # self.bot.threads.append(download_thread)
            download_thread = self.bot.start_twspace_dl_thread()
            print("Started download_space_audio thread.")

            # Allow threads to run for a short period to initiate downloads
            time.sleep(5)

            self.assertTrue(
                download_thread.is_alive(),
                "download_space_audio thread is not running as expected.",
            )
            print("Both threads are running.")

            # Invoke shutdown
            print("Initiating shutdown...")
            self.bot.stop()

            # Wait briefly to allow threads to terminate
            time.sleep(5)  # Adjust based on how long shutdown is expected to take

            # Check if stop_event is set
            # self.assertTrue(self.bot.stop_event.is_set(), "stop_event was not set during shutdown.")
            # print("stop_event has been set.")

            # Check if threads have been terminated
            for thread in self.bot.threads:
                self.assertFalse(
                    thread.is_alive(), f"Thread {thread.name} is still running after shutdown."
                )
                print(f"Thread {thread.name} has been successfully terminated.")

            print("All threads have been successfully terminated.")


if __name__ == "__main__":
    unittest.main()
