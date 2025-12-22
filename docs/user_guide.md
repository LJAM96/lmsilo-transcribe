# Speech-to-Text Server - User Guide

The Speech-to-Text (STT) Server is a powerful, locally-hosted application for transcribing audio and video files using state-of-the-art AI models. It provides a modern web interface for managing transcription jobs, editing transcripts, and analyzing audio content.

## Key Features

### 🎧 High-Quality Transcription
- Uses **Faster-Whisper** for lightning-fast, accurate transcription.
- Supports multiple languages with auto-detection.
- Optional translation to English.

### 🗣️ Speaker Diarization
- Detects and labels different speakers in the audio.
- Visual timeline shows who spoke when.

### 📝 Interactive Transcript Editor
- **Inline Editing**: Double-click any text segment to correct errors instantly.
- **Search & Filter**: Find specific words or speakers.
- **Word-Level Timing**: Click any word to jump to that exact moment in the audio.

### 📦 Batch Processing
- Upload 5+ files at once to trigger **Batch Mode**.
- Monitor batch progress and export all transcripts as a single ZIP file.

### 🎬 Video Subtitles
- Automatically generates SRT and VTT subtitle files.
- **Burn-in Support**: Create a new video file with hardcoded subtitles for social media or playback on devices without subtitle support.

### 📊 Analytics & Insights
- **Word Clouds**: Visualize the most frequent terms in your transcripts.
- **Language Stats**: Track the languages processed over time in the History tab.

### 📱 Mobile Friendly
- Fully responsive design works on desktop, tablet, and mobile.
- Monitor jobs and read transcripts on the go.

## Getting Started

1.  **Upload**: Drag and drop your audio or video file onto the dashboard.
2.  **Configure**: Select your language (or leave Auto) and choose a model (e.g., 'tiny', 'base', 'large-v2').
3.  **Process**: Click "Transcribe". The job will appear in the queue.
4.  **Review**: Once complete, click the job to view the interactive transcript, edit text, or download subtitles.
