# X SpaceCadet

_the first & only x space transcription tool that is able to identify speakers and summarize conversations_

Record, transcribe (with speaker identification), and chat directly with X Space transcripts.

## Features

- **Record X Spaces:** Bot joins the space and records the audio while noting the current speaker.
- **Audio Processing:** Download and process audio using [twspace-dl](https://github.com/HoloArchivists/twspace-dl).
- **Transcription:** Transcribe audio using [Insanely Fast Whisper](https://github.com/Vaibhavs10/insanely-fast-whisper).
- **Speaker Identification:** Identify speakers in the transcript using captured frames and metadata.
- **Chat with Transcript:** OpenAI integration to chat with the transcript.

## Work in Progress

Listening to people ramble on x spaces is often grueling but it is certain that there are diamonds in the rough. For this reason, I searched for tools that recorded spaces but couldn't find anything that was able to actually identify speakers and summarize conversations - so I built a solution myself. I've already dumped too much time into this and it suits my needs but I figured I'd share it in case anyone else finds it useful. Depending on how much interest there is, I'll continue to improve it.

1. **Recording Termination:** Currently, the only way to stop a recording is to kill the application. We're working on implementing a more graceful shutdown method.

2. **Live Spaces Only:** Only works for spaces in progress because the bot needs to join the space and identify speakers in real-time. Would love for this to work with completed/recorded spaces but might be tricky since the speaking animations used to identify speakers aren't as reliable.

3. **User Experience:** The current UX could be significantly improved. Streamlit was chosen to keep development time to a minimum.

4. **Code Quality:** The codebase is pretty shitty but its in an okay place to begin cleaning it up.

## Installation

### Prerequisites

- **Python 3.7 or higher**
- **[Chrome WebDriver](https://chromedriver.chromium.org/downloads):** Required for Selenium to automate browser actions.
- **[ffmpeg](https://ffmpeg.org/download.html):** Needed for audio conversion.
- **X API Key:** Basic plan required for accessing X API endpoints.
- **Hugging Face API Key:** Required for accessing Hugging Face API endpoints.
- **OpenAI API Key:** Needed for chatbot.

### Setup Steps

1. **Clone the Repository:**

   ```sh
   git clone https://github.com/robbie-wasabi/xspacecadet.git
   cd xspacecadet
   ```

2. **Install Dependencies:**

   ```sh
   pip install -r requirements.txt
   ```

3. **Set Up Environment Variables:**

   Create a `.env` file in the root directory and add the following variables:

   - `X_BEARER`: Your X API bearer token.
   - `X_COOKIE_FILE`: Path to your X cookie file.
   - `HF_TOKEN`: Your Hugging Face API token.
   - `OPENAI_API_KEY`: Your OpenAI API key.

   Example `.env` file:

   ```dotenv
   X_BEARER=your_x_bearer_token
   X_COOKIE_FILE=./cookies.txt
   HF_TOKEN=your_hugging_face_token
   OPENAI_API_KEY=your_openai_api_key
   ```

   **Note:** You can obtain these tokens from:

   - **X API Bearer Token:** [X Developer Portal](https://developer.twitter.com/en/portal/dashboard)
   - **X Cookie File:** Use the [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) Chrome extension.
   - **Hugging Face Token:** [Hugging Face Tokens](https://huggingface.co/settings/tokens)
   - **OpenAI API Key:** [OpenAI API Keys](https://platform.openai.com/account/api-keys)

## Usage

XSpaceCadet can be used via a shitty command-line interface or the Streamlit web application.

### Command-Line Interface (CLI)

#### Recording a Space

To record a Space:

```sh
python main.py record <space_id> [cookie_file] [options]
```

**Example:**

```sh
python main.py record https://x.com/i/spaces/AAAAAAAAAAAAA ./cookies.txt
```

#### Transcribing and Identifying Speakers

To transcribe the recorded audio and identify speakers:

```sh
python main.py transcribe <space_id>
```

**Example:**

```sh
python main.py transcribe AAAAAAAAAAAAA
```

#### Fetching Space Metadata

To fetch metadata for a space:

```sh
python main.py fetch-metadata <space_id>
```

**Example:**

```sh
python main.py fetch-metadata AAAAAAAAAAAAA
```

### Streamlit Web App

#### Running the App

Start the Streamlit application:

```sh
streamlit run app.py
```

#### Using the App

1. Open your web browser and navigate to `http://localhost:8501`.
2. Configure your tokens and settings in the sidebar:

   - Hugging Face Token
   - X Bearer Token
   - Path to X Cookie File
   - OpenAI API Key

3. Use the **Record Space** tab to start recording an X Space by entering the Space ID or URL.
4. Use the **Transcribe** tab to process recorded spaces, generate transcripts, and summaries.

## Contributing

Contributions are encouraged (please) just open an issue or submit a pr.

## License

project is licensed under the [MIT License](LICENSE).

## Contact

discord: robbie_wasabi
