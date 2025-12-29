import uuid
import json
import re
import warnings
import os
import shutil

import gspread
import easyocr
from google import genai
from oauth2client.service_account import ServiceAccountCredentials
from fastmcp import FastMCP

mcp = FastMCP("Smart Budget Tracker")
warnings.filterwarnings("ignore", category=UserWarning, message=".*pin_memory.*")

SHEET_NAME = "SmartTracker"
JSON_KEYFILE = "credentials.json"
GEMINI_API_KEY = "AIzaSyAWZEoBoljII8KMfaheiA6tuZPTEDEas2A"

INBOX_FOLDER = "/Users/ashchan/Desktop/Receipt_Inbox"
PROCESSED_FOLDER = "/Users/ashchan/Desktop/Receipts_Processed"

os.makedirs(INBOX_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

sheet = None
client_genai = None
reader = None
SETUP_ERROR = None

try:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
    client_gspread = gspread.authorize(creds)
    sheet = client_gspread.open(SHEET_NAME).sheet1

    client_genai = genai.Client(api_key=GEMINI_API_KEY)
    reader = easyocr.Reader(["en"], gpu=False)
except Exception as e:
    SETUP_ERROR = str(e)


def parse_text_with_gemini(receipt_text: str) -> dict:
    prompt = """
    Extract data from this receipt text. Return ONLY a valid JSON object.
    Required fields:
      - store_name (string)
      - bill_purchase_date (string, prefer YYYY-MM-DD)
      - total_cost (number)
      - tax_amount (number)
      - items: list of { name, price, category }
    If tax not present, use 0.
    """

    response = client_genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=[receipt_text, prompt],
    )

    raw = response.text
    match = re.search(r"``````", raw, re.DOTALL)
    json_str = match.group(1) if match else raw.strip()
    return json.loads(json_str)


@mcp.tool()
def parse_receipt_image(image_path: str) -> str:
    """
    Parse a single receipt image into structured JSON (as a string).
    """
    if SETUP_ERROR:
        return f"Setup error: {SETUP_ERROR}"

    if not os.path.exists(image_path):
        return f"Error: file not found at {image_path}"

    try:
        ocr_result = reader.readtext(image_path, detail=0)
        text = " ".join(ocr_result)
    except Exception as e:
        return f"Error during OCR: {e}"

    try:
        data = parse_text_with_gemini(text)
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Error during Gemini parsing: {e}"


@mcp.tool()
def save_expense_to_sheet(receipt_json: str) -> str:
    """
    Save one parsed receipt JSON into Google Sheets.
    Can be called directly by Claude or by other tools.
    """
    if SETUP_ERROR:
        return f"Setup error: {SETUP_ERROR}"

    try:
        data = json.loads(receipt_json)
    except Exception as e:
        return f"Invalid JSON: {e}"

    receipt_id = str(uuid.uuid4())[:8]

    try:
        items_list = data.get("items", [])
        if not items_list:
            items_list = [
                {
                    "name": "Unspecified Item",
                    "category": "Misc",
                    "price": data.get("total_cost", 0),
                }
            ]

        rows = []
        for item in items_list:
            row = [
                receipt_id,
                data.get("bill_purchase_date", "N/A"),
                data.get("store_name", "Unknown Store"),
                item.get("name", "Unknown"),
                item.get("category", "Misc"),
                item.get("price", 0.0),
                data.get("tax_amount", 0.0),
                data.get("total_cost", 0.0),
            ]
            rows.append(row)

        sheet.append_rows(rows)
        return f"Saved {len(rows)} row(s) with Receipt ID {receipt_id}."
    except Exception as e:
        return f"Error writing to Google Sheet: {e}"


@mcp.tool()
def process_receipt_inbox() -> str:
    """
    Batch process: for each image in INBOX_FOLDER,
    1) parse text with OCR + Gemini,
    2) call save_expense_to_sheet for that receipt,
    3) move the file.
    """
    if SETUP_ERROR:
        return f"Setup error: {SETUP_ERROR}"

    files = [
        f
        for f in os.listdir(INBOX_FOLDER)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]

    if not files:
        return "No receipts found in Inbox folder."

    report = []

    for filename in files:
        file_path = os.path.join(INBOX_FOLDER, filename)

        try:
            ocr_result = reader.readtext(file_path, detail=0)
            text = " ".join(ocr_result)
            data = parse_text_with_gemini(text)
        except Exception as e:
            report.append(f"Failed {filename} during parsing: {e}")
            continue

        # Call save_expense_to_sheet internally
        try:
            receipt_json = json.dumps(data)
            result = save_expense_to_sheet(receipt_json)
        except Exception as e:
            report.append(f"Failed {filename} during saving: {e}")
            continue

        try:
            safe_store = "".join(
                c for c in data.get("store_name", "Store") if c.isalnum()
            )
            safe_date = data.get("bill_purchase_date", "Date")
            new_name = f"{safe_store}_{safe_date}_{filename}"
            dest_path = os.path.join(PROCESSED_FOLDER, new_name)
            shutil.move(file_path, dest_path)
            report.append(f"{filename}: {result} | Moved to {new_name}")
        except Exception as e:
            report.append(f"{filename}: Saved but failed to move file: {e}")

    return "\n".join(report)


@mcp.tool()
def list_saved_receipts(limit: int = 20) -> str:
    """
    List the most recent receipts from the sheet.
    """
    if SETUP_ERROR:
        return f"Setup error: {SETUP_ERROR}"

    try:
        all_values = sheet.get_all_values()
        header, rows = all_values[0], all_values[1:]

        if not rows:
            return "No receipts saved yet."

        rows = rows[-limit:]

        lines = []
        for r in rows:
            receipt_id = r[0] if len(r) > 0 else ""
            date = r[1] if len(r) > 1 else ""
            store = r[2] if len(r) > 2 else ""
            total = r[7] if len(r) > 7 else ""
            lines.append(f"{receipt_id} | {date} | {store} | Total: {total}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error reading from Google Sheet: {e}"


if __name__ == "__main__":
    mcp.run()
