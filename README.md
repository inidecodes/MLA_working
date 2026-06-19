# Multilingual Meeting Assistant (MLA)

## Overview

Multilingual Meeting Assistant (MLA) is an AI-powered meeting intelligence platform designed to automatically transcribe, translate, summarize, and generate Minutes of Meeting (MOM) from recorded or live meeting audio.

The application helps organizations overcome language barriers by supporting multiple Indian languages and converting conversations into structured, actionable meeting outcomes.

---

## Features

###  Speech-to-Text Transcription

* Convert meeting audio into text using AI-based speech recognition.
* Supports uploaded audio recordings.
* High accuracy transcription for multilingual meetings.

###  Multilingual Translation

* Translate meeting transcripts between multiple Indian languages and English.
* Enables collaboration across diverse linguistic teams.

###  Automatic MOM Generation

* Generate professional Minutes of Meeting (MOM) automatically.
* Extract:

  * Meeting Summary
  * Key Discussion Points
  * Decisions Taken
  * Action Items
  * Follow-up Tasks

###  Meeting Search & Retrieval

* Store transcripts and MOMs in SQL Server.
* Retrieve past meetings efficiently.

###  Database Integration

* Secure storage of:

  * Meeting Details
  * Transcripts
  * Translations
  * Generated MOMs
  * User Responses

###  Future Enhancements

* Sentiment Analysis
* Task Assignment Detection
* Deadline Extraction
* Follow-up Email Generation
* Attendance Tracking
* Real-time Meeting Analytics

---

## Technology Stack

### Frontend

* HTML5
* Bootstrap 5
* JavaScript

### Backend

* FastAPI
* Python

### Database

* Microsoft SQL Server Express

### AI & NLP Components

* Whisper (Speech Recognition)
* IndicTrans2 (Translation)
* FastText (Language Detection)
* Ollama
* Llama 3 (MOM Generation)

---

## System Architecture

Meeting Audio
↓
Speech-to-Text (Whisper)
↓
Language Detection
↓
Translation (IndicTrans2)
↓
Transcript Storage (SQL Server)
↓
MOM Generation (Llama 3)
↓
Summary, Action Items & Reports

---

## Project Structure

```text
MLA/
│
├── frontend/
│   ├── html/
│   ├── css/
│   └── js/
│
├── backend/
│   ├── api/
│   ├── services/
│   ├── models/
│   └── database/
│
├── uploads/
├── transcripts/
├── generated_mom/
│
├── requirements.txt
├── main.py
└── README.md
```

---

## Installation

### Clone Repository

```bash
git clone https://github.com/inidecodes/MLA_working.git
cd MLA_working
```

### Create Virtual Environment

```bash
python -m venv venv
```

### Activate Environment

Windows:

```bash
venv\Scripts\activate
```

Linux/Mac:

```bash
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Application

```bash
uvicorn main:app --reload
```

---

## Workflow

1. Upload meeting audio.
2. Generate transcript using Whisper.
3. Translate transcript to selected language.
4. Generate Minutes of Meeting.
5. Store outputs in SQL Server.
6. View, search, and manage meeting records.

---

## Database Storage

### Transcript Storage

* Original Transcript
* Language Information
* Meeting Metadata

### Translation Storage

* Source Language
* Target Language
* Translated Content

### MOM Storage

* Summary
* Action Items
* Decisions
* Meeting Notes

---

## Use Cases

* Corporate Meetings
* HR Discussions
* Government Meetings
* Educational Institutions
* Cross-Language Team Collaboration
* Project Review Meetings

---

## Contributors

Developed as part of the Multilingual Meeting Assistant project to improve meeting productivity through Artificial Intelligence and Natural Language Processing.

---

## License

This project is intended for educational and research purposes. Please review and update the license according to organizational requirements.
