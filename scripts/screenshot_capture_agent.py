"""
Windows/PC Screenshot Ingestion Client for Exam-Kraft CBT.

Captures snipped/screenshot exam questions directly from any screen (PDF reader,
browser, Word, scanned question papers), automatically groups them, packages them
into a structured ZIP file, and uploads them to the Exam-Kraft Question Bank.

Usage:
    python screenshot_capture_agent.py --paper-id <UUID> --server http://localhost:8000 --token <JWT>
"""

import os
import sys
import time
import zipfile
import argparse
from datetime import datetime
from PIL import ImageGrab, Image

try:
    import keyboard  # optional hotkey listener
except ImportError:
    keyboard = None

import requests


class ScreenshotCaptureSession:
    def __init__(self, paper_id: str, server_url: str, auth_token: str, output_dir: str = './captured_snips'):
        self.paper_id = paper_id
        self.server_url = server_url.rstrip('/')
        self.auth_token = auth_token
        self.output_dir = output_dir
        self.captured_files = []
        os.makedirs(self.output_dir, exist_ok=True)

    def grab_clipboard_image(self, index: int) -> str:
        """Grabs the latest snip from Windows Clipboard (Win + Shift + S)."""
        img = ImageGrab.grabclipboard()
        if isinstance(img, Image.Image):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"q{index:03d}_snip_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            img.save(filepath, 'PNG')
            self.captured_files.append(filepath)
            print(f"Captured Clipboard Snip: {filename} ({img.size[0]}x{img.size[1]}px)")
            return filepath
        else:
            print("No image found in clipboard. Use 'Win + Shift + S' to snip a question first!")
            return None

    def create_zip_package(self) -> str:
        """Packages all captured images into a timestamped ZIP archive."""
        if not self.captured_files:
            raise ValueError("No questions captured in this session.")

        zip_path = os.path.join(self.output_dir, f"exam_snips_{self.paper_id[:8]}_{datetime.now().strftime('%Y%m%d%H%M')}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filepath in self.captured_files:
                zf.write(filepath, arcname=os.path.basename(filepath))
        print(f"\nCreated ZIP package: {zip_path} with {len(self.captured_files)} questions.")
        return zip_path

    def upload_to_question_bank(self, zip_path: str, reason: str = 'Windows Screenshot Agent Snips') -> dict:
        """Uploads the ZIP directly to Exam-Kraft API."""
        upload_url = f"{self.server_url}/api/v1/question-papers/{self.paper_id}/upload-zip/"
        headers = {
            'Authorization': f"Bearer {self.auth_token}"
        }
        print(f"Uploading package to: {upload_url}...")
        with open(zip_path, 'rb') as f:
            files = {'file': (os.path.basename(zip_path), f, 'application/zip')}
            data = {'reason': reason}
            response = requests.post(upload_url, headers=headers, files=files, data=data)

        if response.status_code == 201:
            res_data = response.json()
            print("Upload SUCCESS:")
            print(f"   Created questions: {res_data.get('data', {}).get('questions_created', 0)}")
            return res_data
        else:
            print(f"Upload FAILED [{response.status_code}]: {response.text}")
            return {'error': response.text}


def run_interactive_session():
    parser = argparse.ArgumentParser(description="Exam-Kraft Screenshot Capture Agent")
    parser.add_argument('--paper-id', required=True, help="Question Paper UUID")
    parser.add_argument('--server', default="http://localhost:8000", help="Exam-Kraft Backend URL")
    parser.add_argument('--token', required=True, help="JWT Auth Bearer Token")
    parser.add_argument('--reason', default="Windows PC Snip Tool Ingest", help="Upload audit reason")
    args = parser.parse_args()

    session = ScreenshotCaptureSession(args.paper_id, args.server, args.token)
    print("=" * 60)
    print("  EXAM-KRAFT SCREENSHOT CAPTURE AGENT READY")
    print("=" * 60)
    print("Instructions:")
    print(" 1. Open your PDF or Question Paper on screen.")
    print(" 2. Press [Win + Shift + S] (or Cmd + Shift + 4 on Mac) and snip the question.")
    print(" 3. Switch to this terminal and press [ENTER] to save the snip.")
    print(" 4. Type 'u' and press [ENTER] when finished to ZIP and Upload.")
    print(" 5. Type 'q' to quit without uploading.")
    print("=" * 60)

    count = 1
    while True:
        choice = input(f"\n[Q#{count}] Press ENTER after snipping (or 'u' to upload, 'q' to exit): ").strip().lower()
        if choice == 'u':
            if not session.captured_files:
                print("No snips captured yet!")
                continue
            zip_file = session.create_zip_package()
            session.upload_to_question_bank(zip_file, reason=args.reason)
            break
        elif choice == 'q':
            print("Session aborted.")
            break
        else:
            snip = session.grab_clipboard_image(count)
            if snip:
                count += 1

if __name__ == '__main__':
    run_interactive_session()
