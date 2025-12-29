import json
import re
import gspread
import easyocr
from google import genai
from oauth2client.service_account import ServiceAccountCredentials
import warnings

# Suppress the specific 'pin_memory' warning and other Torch/EasyOCR clutter
warnings.filterwarnings("ignore", category=UserWarning, message=".*pin_memory.*")

# 1. SETUP: Google Sheets API
# Replace 'SmartTracker' with the exact name of your Google Sheet
SHEET_NAME = "SmartTracker"
JSON_KEYFILE = "credentials.json"

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
client_gspread = gspread.authorize(creds)
sheet = client_gspread.open(SHEET_NAME).sheet1

# 2. SETUP: Gemini AI and OCR
# Replace with your actual API key
GEMINI_API_KEY = "AIzaSyAWZEoBoljII8KMfaheiA6tuZPTEDEas2A"
client_genai = genai.Client(api_key=GEMINI_API_KEY)
reader = easyocr.Reader(['en'], gpu=False)

def update_inventory_sheet(parsed_data):
    """
    Processes the JSON dictionary and appends rows to Google Sheets.
    """
    try:
        store = parsed_data.get("store_name", "N/A")
        date = parsed_data.get("bill_purchase_date", "N/A")
        total_bill = parsed_data.get("total_cost", 0)
        tax = parsed_data.get("tax_amount", 0) 
        items = parsed_data.get("items", [])


        rows_to_append = []
        for item in items:
            # Format: Date, Store, Item Name, Category, Price, Tax, Total Bill
            row = [
                date,
                store,
                item.get("name", "N/A"),
                item.get("category", "Miscellaneous"),
                item.get("price", 0),
                tax,                
                total_bill
            ]
            rows_to_append.append(row)

        if rows_to_append:
            sheet.append_rows(rows_to_append)
            print(f"Successfully added {len(rows_to_append)} items to the sheet.")
        else:
            print("No items found to add.")

    except Exception as e:
        print(f"Error writing to sheet: {e}")

# 3. EXECUTION FLOW
print("Step 1: Reading image text...")
ocr_result = reader.readtext('bestbuy.png', detail=0)
receipt_context = " ".join(ocr_result)

prompt = """
Extract data from this list of receipt text. 
Return ONLY a valid JSON object. Do not include any introductory text.
The JSON must have: 'store_name', 'bill_purchase_date', 'total_cost', 'tax_amount', and 'items' (a list of objects with 'name', 'price', and 'category').
Examples for category: Electronics, Groceries, Clothing, Entertainment, Miscellaneous.
Also add a seperate column for tax before total cost.
"""

print("Step 2: Sending to Gemini for parsing...")
response = client_genai.models.generate_content(
    model="gemini-2.5-flash",
    contents=[receipt_context, prompt],
)

# 4. JSON CLEANING
# LLMs often wrap JSON in markdown blocks. This regex extracts the raw JSON content.
raw_text = response.text
json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)

if json_match:
    clean_json_str = json_match.group(1)
else:
    clean_json_str = raw_text.strip()

try:
    final_data = json.loads(clean_json_str)
    print("Step 3: Updating Google Sheet...")
    update_inventory_sheet(final_data)
except json.JSONDecodeError as e:
    print(f"Failed to parse JSON: {e}")
    print("Raw text received from AI:")
    print(raw_text)