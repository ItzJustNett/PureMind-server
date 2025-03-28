# API Server with Speech Services and Accessibility Features

This server provides API endpoints for lessons, authentication, profiles, speech services (TTS and STT), and accessibility options for users with different needs.

## Installation

1. Install Python 3.8 or newer
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```
   
   Note: Installing PyAudio may require additional steps:
   - On Windows: `pip install pyaudio`
   - On macOS: `brew install portaudio` then `pip install pyaudio`
   - On Linux: `sudo apt-get install python3-pyaudio` or `sudo apt-get install portaudio19-dev` then `pip install pyaudio`

## Components

### Server

The server component is implemented in `wee.py` and provides all the API endpoints.

### CLI Client

A nice command-line interface for interacting with the server is provided in `nicer-cli-client.py`.

To run the client:
```
python nicer-cli-client.py
```

The CLI client provides a user-friendly interface for:
- User authentication
- Profile management (including accessibility settings)
- Lesson management
- Text-to-Speech conversion
- Speech-to-Text transcription
- Accessibility preferences (support for various conditions)

## Speech Services

The server includes two speech-related endpoints:

### Text-to-Speech (TTS)

Converts text to speech using Google Text-to-Speech (gTTS).

- **Endpoint**: `/api/speech/tts`
- **Method**: POST
- **Request Body**:
  ```json
  {
    "text": "Text to convert to speech",
    "lang": "uk"  // Optional, defaults to Ukrainian
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "audio": "base64-encoded-audio-data",
    "format": "mp3",
    "language": "uk"
  }
  ```

### Speech-to-Text (STT)

Converts speech to text using OpenAI's Whisper Tiny model.

- **Endpoint**: `/api/speech/stt`
- **Method**: POST
- **Request Formats**:
  - **Form data**: Send audio file in the 'audio' field
  - **JSON**: Send base64 encoded audio
    ```json
    {
      "audio": "base64-encoded-audio-data",
      "lang": "uk"  // Optional, defaults to Ukrainian
    }
    ```
- **Response**:
  ```json
  {
    "success": true,
    "text": "Transcribed text",
    "language": "uk"
  }
  ```

## Accessibility Features

The server provides support for users with various conditions through a profile setting. Users can select from the following options:

- None (No special accessibility needs)
- Dyslexia (Дислексія)
- Cerebral Palsy - Motor Impairment (ДЦП - порушення моторики)
- Photosensitivity (Світлочутливість)
- Epilepsy (Епілепсія)
- Color Blindness (Дальтонізм)

These settings can be configured in the user profile and are stored as part of the user's profile information. Client applications can use this information to adjust their display and behavior to accommodate these needs.

## Running the Server

```
python wee.py
```

The server will run on http://0.0.0.0:5000 by default.