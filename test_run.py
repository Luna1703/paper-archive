"""Quick test script for both processors."""
from pathlib import Path
from receipt_processor import process_receipt
from polaroid_processor import process_polaroid

sample_moodboard = r"C:\Users\khano\.gemini\antigravity\brain\07d377b8-9800-4f2b-8c76-dc7350cd1026\.user_uploaded\media_1792519612512_9d642ed9.png"
sample_cassette = r"C:\Users\khano\.gemini\antigravity\brain\07d377b8-9800-4f2b-8c76-dc7350cd1026\.user_uploaded\media_1792519851720_f537f2fe.png"

print("Generating Mode A Receipt...")
receipt_img = process_receipt(
    sample_cassette,
    paper_width=580,
    dither_method="floyd",
    custom_title="TIGRAN SOLOMON'S PAPER ARCHIVE",
    custom_date="1998-04-18 21:40:00"
)
receipt_img.save("output_receipt_test.png")
print(f"Receipt generated: output_receipt_test.png ({receipt_img.size})")

print("Generating Mode B Polaroid...")
polaroid_img = process_polaroid(
    sample_moodboard,
    custom_date="1998-04-18",
    custom_caption="Tigran Solomon's Paper Archive"
)
polaroid_img.save("output_polaroid_test.png", quality=95)
print(f"Polaroid generated: output_polaroid_test.png ({polaroid_img.size})")
