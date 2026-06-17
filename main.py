import os
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pyodbc
import whisper
import traceback 

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
whisper_model = whisper.load_model("medium")

DB_CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=GTBOOK;"
    "DATABASE=AIpromptDB;"
    "Trusted_Connection=yes;"
)

def get_db_cursor():
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
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/transcribe")
async def handle_transcription(
    file: UploadFile = File(None), 
    participant_group: str = Form(...),
    source_type: str = Form("FILE")
):
    if not file:
        raise HTTPException(status_code=400, detail="Audio file asset missing.")

    file_path = os.path.join(TEMP_UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size = os.path.getsize(file_path)
    conn, cursor = get_db_cursor()
    
    try:
        audio_result = whisper_model.transcribe(file_path, fp16=False, verbose=True)
        raw_text = audio_result.get("text", "").strip()
        detected_lang = audio_result.get("language", "en").upper()

        cursor.execute("SELECT ISNULL(MAX(RequestID), 0) + 1 FROM GlbAIRequestDtl")
        new_req_id = cursor.fetchone()[0]

        insert_req_query = """
            INSERT INTO [dbo].[GlbAIRequestDtl] 
            ([RequestID], [PromptID], [ReqType], [ReqPrompt], [ReqFileName], [ReqFileSize], [ReqFilePath], 
             [ReqStatus], [TranslateFrom], [IsJob], [ProductID], [CustID], [IsActive], [CreatedBy], [ModifiedBy], [AudioSourceType], [CreatedDttm], [ModifiedDttm])
            VALUES (?, 1, 'FILE', ?, ?, ?, ?, 'COMPLETED', ?, 0, 1, 1, 1, 99, 99, ?, GETDATE(), GETDATE())
        """
        cursor.execute(insert_req_query, (new_req_id, participant_group, file.filename, file_size, file_path, detected_lang, source_type))
        
        cursor.execute("SELECT ISNULL(MAX(ResponseID), 0) + 1 FROM GlbAIResponseDtl")
        new_res_id = cursor.fetchone()[0]

        insert_res_query = """
            INSERT INTO [dbo].[GlbAIResponseDtl]
            ([ResponseID], [RequestID], [ResSummary], [ProductID], [CustID], [IsActive], [CreatedBy], [ModifiedBy], [CreatedDttm], [ModifiedDttm])
            VALUES (?, ?, ?, 1, 1, 1, 99, 99, GETDATE(), GETDATE())
        """
        cursor.execute(insert_res_query, (new_res_id, new_req_id, raw_text))
        
        conn.commit()
        return {"request_id": new_req_id, "transcription": raw_text, "detected_language": detected_lang}
        
    except Exception as e:
        conn.rollback()
        print("\n" + "="*60)
        print("🚨 CRITICAL DATABASE ERROR DETECTED ON /api/transcribe:")
        print("="*60)
        traceback.print_exc()
        print("="*60 + "\n")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/transcribe-stream")
async def handle_live_save(
    text_content: str = Form(...),
    participant_group: str = Form(...)
):
    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Stream text content empty.")

    conn, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT ISNULL(MAX(RequestID), 0) + 1 FROM GlbAIRequestDtl")
        new_req_id = cursor.fetchone()[0]

        # FIXED: Changed string token to 'LIVE' to prevent truncation mismatch crash completely
        insert_req_query = """
            INSERT INTO [dbo].[GlbAIRequestDtl] 
            ([RequestID], [PromptID], [ReqType], [ReqPrompt], [ReqFileName], [ReqFileSize], [ReqFilePath], 
             [ReqStatus], [TranslateFrom], [IsJob], [ProductID], [CustID], [IsActive], [CreatedBy], [ModifiedBy], [AudioSourceType], [CreatedDttm], [ModifiedDttm])
            VALUES (?, 1, 'LIVE', ?, 'LIVE_DICTATION.txt', 0, 'BROWSER_AUDIO_STREAM', 'COMPLETED', 'EN', 0, 1, 1, 1, 99, 99, 'LIVE', GETDATE(), GETDATE())
        """
        cursor.execute(insert_req_query, (new_req_id, participant_group))
        
        cursor.execute("SELECT ISNULL(MAX(ResponseID), 0) + 1 FROM GlbAIResponseDtl")
        new_res_id = cursor.fetchone()[0]

        insert_res_query = """
            INSERT INTO [dbo].[GlbAIResponseDtl]
            ([ResponseID], [RequestID], [ResSummary], [ProductID], [CustID], [IsActive], [CreatedBy], [ModifiedBy], [CreatedDttm], [ModifiedDttm])
            VALUES (?, ?, ?, 1, 1, 1, 99, 99, GETDATE(), GETDATE())
        """
        cursor.execute(insert_res_query, (new_res_id, new_req_id, text_content))
        
        conn.commit()
        return {"request_id": new_req_id, "status": "SAVED"}
        
    except Exception as e:
        conn.rollback()
        print("\n" + "="*60)
        print("🚨 CRITICAL DATABASE ERROR DETECTED ON /api/transcribe-stream:")
        print("="*60)
        traceback.print_exc()
        print("="*60 + "\n")
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
            raise HTTPException(status_code=404, detail="Transcription content not found.")
        
        transcript_text = row[0]

        structured_mom = (
            f"--- ENGLISH MINUTES OF MEETING ---\n"
            f"Target Scope: Executive Real-Time Operations Sync Alignment\n\n"
            f"Core Decisive Summary Log:\n"
            f"- Reviewed discussion notes: \"{transcript_text[:200]}...\"\n\n"
            f"System Directives:\n"
            f"- Multi-language processing matrix aligned successfully to business logic summary rules."
        )

        cursor.execute("UPDATE GlbAIResponseDtl SET ResHTML = ? WHERE RequestID = ?", (structured_mom, request_id))
        conn.commit()
        return {"mom": structured_mom}
    finally:
        conn.close()

@app.post("/api/translate/{request_id}")
def translate_output(request_id: int, translate_to: str = Form(...)):
    conn, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT ResSummary FROM GlbAIResponseDtl WHERE RequestID = ?", (request_id,))
        transcript_row = cursor.fetchone()
        if not transcript_row:
            raise HTTPException(status_code=404, detail="Record context matched empty.")

        base_text = transcript_row[0]
        translated_text = f"[{translate_to} Engine Translation View Template Output]:\n{base_text}"

        cursor.execute("UPDATE GlbAIResponseDtl SET ResJSON = ? WHERE RequestID = ?", (translated_text, request_id))
        cursor.execute("UPDATE GlbAIRequestDtl SET TranslateTo = ? WHERE RequestID = ?", (translate_to, request_id))
        conn.commit()
        return {"translation": translated_text}
    finally:
        conn.close()

@app.get("/api/history")
def get_history():
    conn, cursor = get_db_cursor()
    try:
        cursor.execute("SELECT RequestID, ReqFileName, AudioSourceType, CreatedDttm FROM GlbAIRequestDtl ORDER BY RequestID DESC")
        rows = cursor.fetchall()
        return [{"request_id": r[0], "file_name": r[1], "source_type": r[2], "date": str(r[3])} for r in rows]
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
            "transcription": row[1],
            "mom": row[2],
            "translation": row[3]
        }
    finally:
        conn.close()