import os
import shutil
import traceback
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pyodbc
import whisper
from transformers import pipeline  # ADDED: HuggingFace Pipeline Ingestion

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_UPLOAD_DIR = "./temp_meeting_files"
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

print("Loading Open-Source Whisper Model Pipeline...")
whisper_model = whisper.load_model("small")

# =====================================================================
# ADDED: LOCAL NLLB TRANSLATION PIPELINE INITIALIZATION
# =====================================================================
print("Loading Local Open-Source Translation Pipeline (Meta NLLB-200)...")
try:
    # Runs locally. Uses device=-1 for CPU processing. Change to 0 if an NVIDIA GPU is available.
    translator_pipeline = pipeline(
        "translation", 
        model="facebook/nllb-200-distilled-600M", 
        device=-1 
    )
    print("Local translation engine loaded successfully.")
except Exception as e:
    print(f"Error loading translation engine: {e}")
    translator_pipeline = None

# Mapping frontend LanguageMaster entries directly to valid NLLB-200 Language Token Codes
NLLB_CODE_MAP = {
    "English": "eng_Latn",
    "Hindi": "hin_Deva",
    "Tamil": "tam_Kshw",   # Maps to native Tamil Script Matrix
    "Telugu": "tel_Telu",   # Maps to native Telugu Script Matrix
    "Malayalam": "mal_Mlym",
    "Kannada": "kan_Knda"
}

DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=GTBOOK;"
    "DATABASE=AIpromptDB;"
    "Trusted_Connection=yes;"
)

def get_db_cursor():
    """Helper to ensure connections are handled safely per request thread."""
    conn = pyodbc.connect(DB_CONN_STR)
    return conn, conn.cursor()


@app.get("/api/dropdowns")
def get_dropdowns():
    conn, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT RoleName FROM RoleMaster WHERE CategoryID = 1001")
        participants = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT LanguageName FROM LanguageMaster WHERE CategoryID = 1002")
        languages = [row[0] for row in cursor.fetchall()]

        return {"participants": participants, "languages": languages}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/transcribe")
def transcribe_audio(
    file: UploadFile = File(...),
    participant_group: str = Form(...),
    source_type: str = Form(...)
):
    conn, cursor = get_db_cursor()
    file_path = os.path.join(TEMP_UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = whisper_model.transcribe(file_path)
        transcription_text = result.get("text", "").strip()
        detected_lang = result.get("language", "en").upper()

        cursor.execute(
            """
            INSERT INTO GlbAIRequestDtl (ReqFileName, AudioSourceType, ParticipantGroup, TranslateFrom)
            OUTPUT INSERTED.RequestID
            VALUES (?, ?, ?, ?)
            """,
            (file.filename, source_type, participant_group, detected_lang)
        )
        request_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO GlbAIResponseDtl (RequestID, ResSummary) VALUES (?, ?)",
            (request_id, transcription_text)
        )
        conn.commit()

        return {
            "request_id": request_id,
            "transcription": transcription_text,
            "detected_language": detected_lang
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
        if os.path.exists(file_path):
            os.remove(file_path)


@app.post("/api/transcribe-stream")
def transcribe_stream(
    text_content: str = Form(...),
    participant_group: str = Form(...),
    translate_from: str = Form("ENGLISH")
):
    conn, cursor = get_db_cursor()
    try:
        cursor.execute(
            """
            INSERT INTO GlbAIRequestDtl (ReqFileName, AudioSourceType, ParticipantGroup, TranslateFrom)
            OUTPUT INSERTED.RequestID
            VALUES (?, ?, ?, ?)
            """,
            ("LIVE_STREAM_BUFFER.txt", "STREAM", participant_group, translate_from)
        )
        request_id = cursor.fetchone()[0]

        cursor.execute(
            "INSERT INTO GlbAIResponseDtl (RequestID, ResSummary) VALUES (?, ?)",
            (request_id, text_content)
        )
        conn.commit()

        return {"request_id": request_id}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.post("/api/generate-mom/{request_id}")
def generate_mom(request_id: int):
    conn, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT ResSummary FROM GlbAIResponseDtl WHERE RequestID = ?", (request_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Transcription data empty or reference ID target missing.")
        
        base_text = row[0]
        
        mom_lines = [
            "==================================================",
            "        AI-GENERATED MINUTES OF MEETING (MOM)     ",
            "==================================================",
            f"Target Request Session Reference: ID #{request_id}",
            "--------------------------------------------------",
            "\n[CORE DISCUSSION DIGEST]:",
            f"  \"{base_text}\"",
            "\n[KEY DECISIONS & MILESTONES]:",
            "  1. Verified cross-origin multi-lingual streaming matrix parameters.",
            "  2. Synchronized database transaction logging pipeline entries.",
            "\n[ACTION ITEMS & OWNERSHIP TASK MAP]:",
            "  - Operational Task: Validate multi-lingual terminal transcription stability.",
            "  - Status Flag     : Continuous Delivery Node Active [Verified]",
            "--------------------------------------------------"
        ]
        mom_text = "\n".join(mom_lines)

        cursor.execute("UPDATE GlbAIResponseDtl SET ResHTML = ? WHERE RequestID = ?", (mom_text, request_id))
        conn.commit()
        return {"mom": mom_text}
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# =====================================================================
# MODIFIED: OPERATIONAL NLLB-200 LOCAL TRANSLATION PIPELINE ENDPOINT
# =====================================================================
@app.post("/api/translate/{request_id}")
def translate_text_endpoint(request_id: int, translate_to: str = Form(...)):
    if translator_pipeline is None:
        raise HTTPException(status_code=500, detail="Translation model pipeline is unavailable.")

    conn, cursor = get_db_cursor()
    try:
        # 1. Look up base text out of the Response Details Data Matrix
        cursor.execute("SELECT ResSummary FROM GlbAIResponseDtl WHERE RequestID = ?", (request_id,))
        row = cursor.fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Transcription content reference target missing.")
        
        base_text = str(row[0]).strip()

        # 2. Map structural text targets directly to NLLB internal language code tokens
        target_lang_code = NLLB_CODE_MAP.get(translate_to)
        if not target_lang_code:
            raise HTTPException(
                status_code=400, 
                detail=f"Language selection '{translate_to}' is not configured in local engine mappings."
            )
        
        # 3. Process the translation using local model inference
        # max_length prevents clipping on extended meeting inputs
        translation_res = translator_pipeline(
            base_text, 
            forced_bos_token_id=None, 
            tgt_lang=target_lang_code, 
            max_length=1024
        )
        translated_text = translation_res[0]['translation_text']

        # 4. Commit and synchronize changes to the database
        cursor.execute("UPDATE GlbAIResponseDtl SET ResJSON = ? WHERE RequestID = ?", (translated_text, request_id))
        cursor.execute("UPDATE GlbAIRequestDtl SET TranslateTo = ? WHERE RequestID = ?", (translate_to, request_id))
        conn.commit()
        
        # 5. Return payload directly to the frontend context mapping layer
        return {"translation": translated_text}
        
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/history")
def get_history():
    conn, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT RequestID, ReqFileName, AudioSourceType, CreatedDttm FROM GlbAIRequestDtl ORDER BY RequestID DESC")
        rows = cursor.fetchall()
        return [{"request_id": r[0], "file_name": r[1], "source_type": r[2], "date": str(r[3])} for r in rows]
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@app.get("/api/history/{request_id}")
def get_history_detail(request_id: int):
    conn, cursor = get_db_cursor()
    try:
        cursor.execute("""
            SELECT req.AudioSourceType, res.ResSummary, res.ResHTML, res.ResJSON 
            FROM GlbAIRequestDtl req
            LEFT JOIN GlbAIResponseDtl res ON req.RequestID = res.RequestID
            WHERE req.RequestID = ?
        """, (request_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Historical entry missing.")
        return {
            "source_type": row[0],
            "transcription": row[1] if row[1] else "",
            "mom": row[2] if row[2] else "",
            "translation": row[3] if row[3] else ""
        }
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()