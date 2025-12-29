import easyocr

reader = easyocr.Reader(['en'], gpu=False)
ocr_result = reader.readtext('bestbuy.png', detail=0)

print(ocr_result)