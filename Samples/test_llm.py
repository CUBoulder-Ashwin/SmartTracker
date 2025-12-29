from google import genai

content = """
['BEST', 'BUY', '(866)-237-8289', '6075 Mavis Rd Unit', '1,', 'Mississauga', 'ON LSR 4G6', 'PRODUCT SERIAL # 4208447', 'Sony WFIOOOXMS In-Ear Noise $373,40', 'Cance] 1', 'ing True', 'Wireless Earbuds', 'Black', 'Subtota|', '$373, 40', 'Tax/HST', '$42.96', 'Tota]', '$416,36', 'Card number', '**kk ** **** 4922', 'Card type', 'Credit', 'Card entry', 'Chip', 'Date/time', '02/02/2025 06:51 PM', 'Reference #', '62845289260246240685C', 'Status', 'APPROVED', '02/02/2025,', '06:51:54 PM', 'ITEMS  SOLD']
"""
prompt = """
Extract data from this list of receipt text. 
Return ONLY a valid JSON object. Do not include any introductory text.
The JSON must have: 'store_name', 'bill_purchase_date', 'total_cost', and 'items' (a list of objects with 'name', 'price', and 'category').
No need for bill purchase time.
Examples for category: Electronics, Groceries, Clothing, Entertainment, Miscellaneous.
Also add a seperate column for tax before total cost.
"""

GEMINI_API_KEY = "ADD_YOUR_API_KEY_HERE"
client_genai = genai.Client(api_key=GEMINI_API_KEY)

response = client_genai.models.generate_content(
    model="gemini-2.5-flash",
    contents=[content,prompt]
)
print(response.text)